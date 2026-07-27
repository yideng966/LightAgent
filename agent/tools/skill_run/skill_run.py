"""Run declared Skill Hub entrypoints through a constrained subprocess broker."""

import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.skills.runtime import build_single_skill_runtime_env
from agent.tools.base_tool import BaseTool, ToolResult
from common.log import logger


_AUDIT_LOCK = threading.Lock()
_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
_RESERVED_ENV_NAMES = {
    "HOME", "PATH", "PYTHONHOME", "PYTHONPATH", "NODE_PATH", "TMP", "TEMP", "TMPDIR",
}


class SkillRun(BaseTool):
    name = "skill_run"
    description = (
        "执行当前请求技能快照中声明的结构化入口。只能调用 SKILL.md lightagent.entrypoints "
        "中存在的入口，不能执行任意命令。"
    )
    params = {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "技能名称"},
            "entrypoint": {"type": "string", "description": "声明的入口名称"},
            "arguments": {
                "type": "array",
                "items": {"type": "string"},
                "description": "传给入口的参数列表，不经过 shell 解析",
                "default": [],
            },
        },
        "required": ["skill_name", "entrypoint", "arguments"],
    }

    def __init__(self, config=None):
        self.config = dict(config or {})
        self.cwd = self.config.get("cwd")
        self._skill_snapshot = {}

    def set_skill_snapshot(self, snapshot):
        self._skill_snapshot = dict(snapshot or {})

    def execute(self, params):
        started = time.monotonic()
        skill_name = str(params.get("skill_name") or "")
        entrypoint_name = str(params.get("entrypoint") or "")
        arguments = params.get("arguments")
        if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
            return ToolResult.fail("arguments 必须是字符串数组")
        skill = self._skill_snapshot.get(skill_name)
        if not skill:
            return ToolResult.fail(f"当前请求快照中不存在技能 {skill_name}")
        entrypoints = (skill.frontmatter.get("lightagent") or {}).get("entrypoints") or []
        entrypoint = next((item for item in entrypoints if item.get("name") == entrypoint_name), None)
        if not entrypoint:
            return ToolResult.fail(f"技能 {skill_name} 未声明入口 {entrypoint_name}")
        try:
            command, env, temp_dir, timeout, output_limit = self._prepare(
                skill, entrypoint, arguments
            )
            return self._run(
                skill_name, entrypoint_name, command, env, temp_dir,
                timeout, output_limit, entrypoint, started,
            )
        except Exception as exc:
            self._audit(skill_name, entrypoint_name, started, "rejected", str(exc))
            return ToolResult.fail(str(exc))

    def _prepare(self, skill, entrypoint, arguments):
        root = Path(skill.base_dir).resolve()
        script = (root / str(entrypoint.get("path") or "")).resolve()
        if root not in script.parents or not script.is_file() or script.is_symlink():
            raise ValueError("入口路径越界、不存在或为符号链接")
        constraints = entrypoint.get("arguments") or {}
        minimum = int(constraints.get("min_items", 0))
        maximum = int(constraints.get("max_items", 0))
        max_length = int(constraints.get("max_length", 2048))
        if len(arguments) < minimum or len(arguments) > maximum:
            raise ValueError(f"入口参数数量必须在 {minimum} 到 {maximum} 之间")
        if any(len(item) > max_length or "\x00" in item for item in arguments):
            raise ValueError("入口参数过长或包含空字符")
        runtime = entrypoint.get("runtime")
        if runtime == "python":
            command = [sys.executable, str(script)]
        elif runtime == "node":
            node = shutil.which("node")
            if not node:
                raise ValueError("当前环境缺少 Node.js")
            command = [node, str(script)]
        elif runtime == "executable":
            if not os.access(script, os.X_OK):
                raise ValueError("声明的 executable 入口没有执行权限")
            command = [str(script)]
        else:
            raise ValueError("入口 runtime 无效")
        workspace = os.path.abspath(self.config.get("skill_workspace") or self.cwd or os.getcwd())
        data_dir = os.path.join(workspace, "skill-data", skill.name)
        config_dir = os.path.join(workspace, "skill-config", skill.name)
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)
        temp_root = os.path.join(workspace, "tmp")
        os.makedirs(temp_root, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix=f"skill-{skill.name}-", dir=temp_root)
        replacements = {
            "<workspace>": workspace,
            "<skill_data>": data_dir,
            "<skill_config>": config_dir,
            "<temp>": temp_dir,
        }
        expanded = []
        for argument in arguments:
            value = argument
            for placeholder, replacement in replacements.items():
                value = value.replace(placeholder, replacement)
            expanded.append(value)
        command.extend(expanded)
        allowed_env = (skill.frontmatter.get("requirements") or {}).get("env", [])
        invalid_env = [
            name for name in allowed_env
            if not isinstance(name, str)
            or not _ENV_NAME_RE.fullmatch(name)
            or name in _RESERVED_ENV_NAMES
            or name.startswith("LIGHTAGENT_")
        ]
        if invalid_env:
            raise ValueError(f"技能声明了不允许注入的环境变量: {', '.join(map(str, invalid_env))}")
        env = build_single_skill_runtime_env(workspace, skill.name, {
            "PATH": os.environ.get("PATH", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", ""),
            "TZ": os.environ.get("TZ", ""),
            **{name: os.environ[name] for name in allowed_env if name in os.environ},
            "HOME": temp_dir,
            "TMPDIR": temp_dir,
            "LIGHTAGENT_WORKSPACE": workspace,
            "LIGHTAGENT_SKILL_DATA": data_dir,
            "LIGHTAGENT_SKILL_CONFIG": config_dir,
            "LIGHTAGENT_SKILL_TEMP": temp_dir,
        })
        timeout = max(1, min(600, int(entrypoint.get("timeout_seconds", 60))))
        output_limit = max(1024, min(1024 * 1024, int(entrypoint.get("max_output_bytes", 262144))))
        return command, env, temp_dir, timeout, output_limit

    def _run(self, skill_name, entrypoint_name, command, env, temp_dir, timeout, output_limit, entrypoint, started):
        process = None
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        output_exceeded = threading.Event()
        buffer_lock = threading.Lock()

        def reader(label, stream):
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                with buffer_lock:
                    remaining = output_limit - sum(len(value) for value in buffers.values())
                    if remaining <= 0:
                        output_exceeded.set()
                        break
                    buffers[label].extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        output_exceeded.set()
                        break
                if output_exceeded.is_set() and process and process.poll() is None:
                    _terminate_process(process)
                    break

        try:
            process = subprocess.Popen(
                command,
                cwd=temp_dir,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                preexec_fn=_resource_limits(entrypoint) if os.name == "posix" else None,
                start_new_session=os.name == "posix",
            )
            threads = [
                threading.Thread(target=reader, args=("stdout", process.stdout), daemon=True),
                threading.Thread(target=reader, args=("stderr", process.stderr), daemon=True),
            ]
            for thread in threads:
                thread.start()
            try:
                return_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _terminate_process(process)
                process.wait()
                for thread in threads:
                    thread.join(timeout=1)
                self._audit(skill_name, entrypoint_name, started, "timeout", f"超过 {timeout} 秒")
                return ToolResult.fail(f"技能入口执行超时（{timeout} 秒）")
            for thread in threads:
                thread.join(timeout=1)
            stdout = bytes(buffers["stdout"]).decode("utf-8", errors="replace")
            stderr = bytes(buffers["stderr"]).decode("utf-8", errors="replace")
            if output_exceeded.is_set():
                self._audit(skill_name, entrypoint_name, started, "output_limit", "输出超过限制")
                return ToolResult.fail(f"技能入口输出超过 {output_limit} 字节限制")
            if return_code != 0:
                detail = (stderr or stdout or f"exit {return_code}").strip()
                self._audit(skill_name, entrypoint_name, started, "failed", detail[-500:])
                return ToolResult.fail(detail)
            self._audit(skill_name, entrypoint_name, started, "success", "")
            return ToolResult.success(stdout.strip())
        finally:
            if process and process.poll() is None:
                _terminate_process(process)
                process.wait()
            if process:
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _audit(self, skill_name, entrypoint, started, status, detail):
        workspace = os.path.abspath(self.config.get("skill_workspace") or self.cwd or os.getcwd())
        path = Path(workspace, ".skillhub", "runner-audit.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "skill": skill_name,
            "entrypoint": entrypoint,
            "status": status,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "detail": str(detail or "")[:500],
            "isolation": "process",
        }
        with _AUDIT_LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("[SkillRunner] %s/%s %s", skill_name, entrypoint, status)


def _terminate_process(process):
    """Terminate the whole POSIX process group, falling back to the direct child."""
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except (ProcessLookupError, PermissionError, OSError):
        if process.poll() is None:
            process.kill()


def _resource_limits(entrypoint):
    memory = max(64, min(2048, int(entrypoint.get("max_memory_mb", 512)))) * 1024 * 1024
    processes = max(1, min(64, int(entrypoint.get("max_processes", 16))))
    timeout = max(1, min(600, int(entrypoint.get("timeout_seconds", 60))))
    existing_tasks = _current_uid_task_count()

    def apply_limits():
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
            resource.setrlimit(resource.RLIMIT_CPU, (timeout + 1, timeout + 1))
            if hasattr(resource, "RLIMIT_NPROC") and existing_tasks is not None:
                _, hard_limit = resource.getrlimit(resource.RLIMIT_NPROC)
                task_limit = existing_tasks + processes
                if hard_limit != resource.RLIM_INFINITY:
                    task_limit = min(task_limit, hard_limit)
                resource.setrlimit(resource.RLIMIT_NPROC, (task_limit, hard_limit))
        except Exception:
            pass

    return apply_limits


def _current_uid_task_count():
    """Return visible Linux UID tasks when RLIMIT_NPROC can be applied safely."""
    if os.name != "posix" or not sys.platform.startswith("linux"):
        return None
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return None
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8")
        if any(marker in cgroup for marker in ("docker", "containerd", "kubepods", "libpod")):
            return None
        real_uid = str(os.getuid())
        total = 0
        for status_path in Path("/proc").glob("[0-9]*/status"):
            try:
                fields = dict(
                    line.split(":", 1)
                    for line in status_path.read_text(encoding="utf-8").splitlines()
                    if ":" in line
                )
                if fields.get("Uid", "").split()[:1] == [real_uid]:
                    total += int(fields.get("Threads", "1"))
            except (OSError, ValueError):
                continue
        return total or None
    except (OSError, ValueError):
        return None
