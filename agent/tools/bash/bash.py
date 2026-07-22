"""
Bash tool - Execute bash commands
"""

import os
import re
import signal
import sys
import subprocess
import tempfile
import threading
import time
from typing import Dict, Any

from agent.tools.base_tool import BaseTool, ToolResult
from agent.tools.utils.truncate import truncate_tail, format_size, DEFAULT_MAX_LINES, DEFAULT_MAX_BYTES
from common.log import logger
from common.utils import expand_path


class Bash(BaseTool):
    """Tool for executing bash commands"""

    _IS_WIN = sys.platform == "win32"
    _PROGRESS_MAX_BYTES = 4 * 1024
    _PROGRESS_INTERVAL = 0.5
    # cmd.exe command line limit is ~8191 chars; rewrite python -c above this.
    _WIN_CMD_SAFE_LEN = 7000

    name: str = "bash"
    description: str = f"""Execute a bash command in the current working directory. Returns stdout and stderr. Output is truncated to last {DEFAULT_MAX_LINES} lines or {DEFAULT_MAX_BYTES // 1024}KB (whichever is hit first). If truncated, full output is saved to a temp file.
{'''
PLATFORM: Windows (cmd.exe). Do NOT use Unix-only commands like grep, head, tail, sed, awk.
''' if _IS_WIN else ''}
ENVIRONMENT: All API keys from env_config are auto-injected. Use $VAR_NAME directly.

SAFETY:
- Freely create/modify/delete files within the workspace
- For destructive commands out of workspace, explain and confirm first"""

    params: dict = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Bash command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (optional, default: 30)"
            }
        },
        "required": ["command"]
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.cwd = self.config.get("cwd", os.getcwd())
        # Ensure working directory exists
        if not os.path.exists(self.cwd):
            os.makedirs(self.cwd, exist_ok=True)
        self.default_timeout = self.config.get("timeout", 30)
        # Enable safety mode by default (can be disabled in config)
        self.safety_mode = self.config.get("safety_mode", True)

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute a bash command
        
        :param args: Dictionary containing the command and optional timeout
        :return: Command output or error
        """
        command = args.get("command", "").strip()
        timeout = args.get("timeout", self.default_timeout)

        if not command:
            return ToolResult.fail("Error: command parameter is required")

        # Security check: Prevent direct access to the credential file
        if re.search(r'\.lightagent[/\\]\.env', command):
            return ToolResult.fail(
                "Error: Access denied. API keys and credentials must be accessed through the env_config tool only."
            )

        # Optional safety check - only warn about extremely dangerous commands
        if self.safety_mode:
            warning = self._get_safety_warning(command)
            if warning:
                return ToolResult.fail(
                    f"Safety Warning: {warning}\n\nIf you believe this command is safe and necessary, please ask the user for confirmation first, explaining what the command does and why it's needed.")

        try:
            # Prepare environment with .env file variables
            env = os.environ.copy()
            
            # Load environment variables from ~/.lightagent/.env if it exists
            env_file = expand_path("~/.lightagent/.env")
            dotenv_vars = {}
            if os.path.exists(env_file):
                try:
                    from dotenv import dotenv_values
                    dotenv_vars = dotenv_values(env_file)
                    env.update(dotenv_vars)
                    logger.debug(f"[Bash] Loaded {len(dotenv_vars)} variables from {env_file}")
                except ImportError:
                    logger.debug("[Bash] python-dotenv not installed, skipping .env loading")
                except Exception as e:
                    logger.debug(f"[Bash] Failed to load .env: {e}")

            # getuid() only exists on Unix-like systems
            if hasattr(os, 'getuid'):
                logger.debug(f"[Bash] Process UID: {os.getuid()}")
            else:
                logger.debug(f"[Bash] Process User: {os.environ.get('USERNAME', os.environ.get('USER', 'unknown'))}")
            
            # Temp script written for long `python -c` commands (Windows only),
            # cleaned up after execution.
            temp_script_path = None

            # On Windows, convert $VAR references to %VAR% for cmd.exe
            if self._IS_WIN:
                env["PYTHONIOENCODING"] = "utf-8"
                command = self._convert_env_vars_for_windows(command, dotenv_vars)
                # cmd.exe has an ~8191 char command line limit. Long
                # `python -c "..."` commands silently fail, so spill the inline
                # code into a temp .py file and run that instead.
                if len(command) > self._WIN_CMD_SAFE_LEN:
                    command, temp_script_path = self._rewrite_long_python_c(command)
                if command and not command.strip().lower().startswith("chcp"):
                    command = f"chcp 65001 >nul 2>&1 && {command}"

            try:
                result = self._run_streaming(
                    command,
                    timeout,
                    env,
                    dotenv_vars,
                )
            finally:
                if temp_script_path:
                    try:
                        os.remove(temp_script_path)
                    except OSError:
                        pass
            
            logger.debug(f"[Bash] Exit code: {result.returncode}")
            logger.debug(f"[Bash] Stdout length: {len(result.stdout)}")
            logger.debug(f"[Bash] Stderr length: {len(result.stderr)}")
            
            # Workaround for exit code 126 with no output
            if result.returncode == 126 and not result.stdout and not result.stderr:
                logger.warning(f"[Bash] Exit 126 with no output - trying alternative execution method")
                # Try using argument list instead of shell=True
                import shlex
                try:
                    parts = shlex.split(command)
                    if len(parts) > 0:
                        logger.info(f"[Bash] Retrying with argument list: {parts[:3]}...")
                        retry_result = subprocess.run(
                            parts,
                            cwd=self.cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            timeout=timeout,
                            env=env
                        )
                        logger.debug(f"[Bash] Retry exit code: {retry_result.returncode}, stdout: {len(retry_result.stdout)}, stderr: {len(retry_result.stderr)}")
                        
                        # If retry succeeded, use retry result
                        if retry_result.returncode == 0 or retry_result.stdout or retry_result.stderr:
                            result = retry_result
                        else:
                            # Both attempts failed - check if this is openai-image-vision skill
                            if 'openai-image-vision' in command or 'vision.sh' in command:
                                # Create a mock result with helpful error message
                                from types import SimpleNamespace
                                result = SimpleNamespace(
                                    returncode=1,
                                    stdout='{"error": "图片无法解析", "reason": "该图片格式可能不受支持，或图片文件存在问题", "suggestion": "请尝试其他图片"}',
                                    stderr=''
                                )
                                logger.info(f"[Bash] Converted exit 126 to user-friendly image error message for vision skill")
                except Exception as retry_err:
                    logger.warning(f"[Bash] Retry failed: {retry_err}")

            # When command succeeds with stdout, keep output clean (stderr goes to server log only).
            # When command fails or stdout is empty, include stderr so the agent can diagnose.
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout
                if result.stderr:
                    logger.info(f"[Bash] stderr (not forwarded): {result.stderr[:500]}")
            else:
                output = result.stdout
                if result.stderr:
                    output += "\n" + result.stderr

            # Check if we need to save full output to temp file
            temp_file_path = None
            total_bytes = len(output.encode('utf-8'))

            if total_bytes > DEFAULT_MAX_BYTES:
                # Save full output to temp file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log', prefix='bash-') as f:
                    f.write(output)
                    temp_file_path = f.name

            # Apply tail truncation
            truncation = truncate_tail(output)
            output_text = truncation.content or "(no output)"

            # Build result
            details = {}

            if truncation.truncated:
                details["truncation"] = truncation.to_dict()
                if temp_file_path:
                    details["full_output_path"] = temp_file_path

                # Build notice
                start_line = truncation.total_lines - truncation.output_lines + 1
                end_line = truncation.total_lines

                if truncation.last_line_partial:
                    # Edge case: last line alone > 30KB
                    last_line = output.split('\n')[-1] if output else ""
                    last_line_size = format_size(len(last_line.encode('utf-8')))
                    output_text += f"\n\n[Showing last {format_size(truncation.output_bytes)} of line {end_line} (line is {last_line_size}). Full output: {temp_file_path}]"
                elif truncation.truncated_by == "lines":
                    output_text += f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines}. Full output: {temp_file_path}]"
                else:
                    output_text += f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines} ({format_size(DEFAULT_MAX_BYTES)} limit). Full output: {temp_file_path}]"

            # Check exit code
            if result.returncode != 0:
                output_text += f"\n\nCommand exited with code {result.returncode}"
                return ToolResult.fail({
                    "output": output_text,
                    "exit_code": result.returncode,
                    "details": details if details else None
                })

            return ToolResult.success({
                "output": output_text,
                "exit_code": result.returncode,
                "details": details if details else None
            })

        except subprocess.TimeoutExpired:
            return ToolResult.fail(f"Error: Command timed out after {timeout} seconds")
        except Exception as e:
            return ToolResult.fail(f"Error executing command: {str(e)}")

    def _run_streaming(self, command: str, timeout: int, env: dict, dotenv_vars: dict):
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=not self._IS_WIN,
        )
        stdout_chunks, stderr_chunks = [], []
        recent = bytearray()
        recent_lock = threading.Lock()

        def drain(stream, chunks):
            while True:
                chunk = os.read(stream.fileno(), 4096)
                if not chunk:
                    break
                chunks.append(chunk)
                with recent_lock:
                    recent.extend(chunk)
                    if len(recent) > self._PROGRESS_MAX_BYTES:
                        del recent[:-self._PROGRESS_MAX_BYTES]

        readers = [
            threading.Thread(target=drain, args=(process.stdout, stdout_chunks), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, stderr_chunks), daemon=True),
        ]
        for reader in readers:
            reader.start()

        started = time.monotonic()
        last_reported_at = started
        last_snapshot = None
        try:
            while process.poll() is None:
                now = time.monotonic()
                elapsed = now - started
                if elapsed >= timeout:
                    self._kill_process(process)
                    raise subprocess.TimeoutExpired(command, timeout)
                if elapsed >= self._PROGRESS_INTERVAL and now - last_reported_at >= self._PROGRESS_INTERVAL:
                    with recent_lock:
                        snapshot = bytes(recent).decode("utf-8", errors="replace")
                    snapshot = self._redact_progress(snapshot, dotenv_vars)
                    if snapshot and snapshot != last_snapshot:
                        self.report_progress(snapshot)
                        last_snapshot = snapshot
                    last_reported_at = now
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                self._kill_process(process)
            process.wait()
            join_deadline = time.monotonic() + 5
            for reader in readers:
                reader.join(timeout=max(0, join_deadline - time.monotonic()))

        from types import SimpleNamespace
        return SimpleNamespace(
            returncode=process.returncode,
            stdout=b"".join(stdout_chunks).decode("utf-8", errors="replace"),
            stderr=b"".join(stderr_chunks).decode("utf-8", errors="replace"),
        )

    def _kill_process(self, process):
        if self._IS_WIN:
            try:
                result = subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0 and process.poll() is None:
                    process.kill()
            except (OSError, subprocess.SubprocessError):
                if process.poll() is None:
                    process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (PermissionError, ProcessLookupError):
                if process.poll() is None:
                    process.kill()

    @staticmethod
    def _redact_progress(text: str, dotenv_vars: dict) -> str:
        text = re.sub(
            r'(?i)\b(API_KEY|TOKEN|PASSWORD|AUTHORIZATION)\s*=\s*[^\s]+',
            lambda match: f"{match.group(1)}=[REDACTED]",
            text,
        )
        for value in dotenv_vars.values():
            value = str(value or "")
            if len(value) >= 6:
                text = text.replace(value, "[REDACTED]")
        return text

    def _get_safety_warning(self, command: str) -> str:
        """
        Get safety warning for absolutely catastrophic commands only.
        Keep the blocklist minimal so the agent retains maximum freedom.

        :param command: Command to check
        :return: Warning message if dangerous, empty string if safe
        """
        # Tokenize to avoid substring false positives (e.g. `rm -rf /tmp/x`
        # must not match `rm -rf /`).
        tokens = command.lower().split()

        # `rm -rf /` or `rm -rf /*` targeting the real root.
        for i, tok in enumerate(tokens):
            if tok != "rm":
                continue
            has_rf = False
            for j in range(i + 1, len(tokens)):
                t = tokens[j]
                if t.startswith("-") and "r" in t and "f" in t:
                    has_rf = True
                elif t in ("--recursive", "--force"):
                    continue
                elif t in ("/", "/*"):
                    if has_rf:
                        return "This command will delete the entire filesystem"
                    break
                else:
                    break

        # Disk wiping
        if "if=/dev/zero" in command.lower() and "dd " in command.lower():
            return "This command can destroy disk data"

        # Power control - match only as a standalone word (\b enforces word boundary)
        if re.search(r'\b(shutdown|reboot|halt|poweroff)\b', command.lower()):
            return "This command will shut down or restart the system"

        return ""

    @staticmethod
    def _convert_env_vars_for_windows(command: str, dotenv_vars: dict) -> str:
        """
        Convert bash-style $VAR / ${VAR} references to cmd.exe %VAR% syntax.
        Only converts variables loaded from .env (user-configured API keys etc.)
        to avoid breaking $PATH, jq expressions, regex, etc.
        """
        if not dotenv_vars:
            return command

        def replace_match(m):
            var_name = m.group(1) or m.group(2)
            if var_name in dotenv_vars:
                return f"%{var_name}%"
            return m.group(0)

        return re.sub(r'\$\{(\w+)\}|\$(\w+)', replace_match, command)

    @staticmethod
    def _rewrite_long_python_c(command: str):
        """
        Rewrite `python -c "<code>"` into `python <tempfile>` to bypass the
        cmd.exe command line length limit on Windows.

        Returns (new_command, temp_file_path). On any parse failure the original
        command and None are returned, so behavior is unchanged when unmatched.
        """
        # Match: <python|python3|py> [flags] -c "<code>" (single or double quoted)
        m = re.search(
            r'^(?P<prefix>.*?\b(?:python3?|py)\b[^\n]*?\s-c\s+)'
            r'(?P<quote>["\'])(?P<code>.*)(?P=quote)\s*(?P<suffix>.*)$',
            command,
            re.DOTALL,
        )
        if not m:
            return command, None

        quote = m.group("quote")
        code = m.group("code")
        # Reverse common shell-level escaping of the quote char inside the code.
        code = code.replace("\\" + quote, quote)

        try:
            fd, path = tempfile.mkstemp(suffix=".py", prefix="bash-pyc-")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(code)
        except OSError:
            return command, None

        prefix = m.group("prefix")
        # Drop the trailing "-c " from the prefix, keep the interpreter + flags.
        interp = re.sub(r'\s-c\s+$', ' ', prefix).rstrip()
        suffix = m.group("suffix").strip()
        new_command = f'{interp} "{path}"'
        if suffix:
            new_command += f' {suffix}'
        return new_command, path
