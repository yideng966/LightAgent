"""Subprocess client for the Node.js Wechaty sidecar."""

import json
import os
import subprocess
import threading
from typing import Callable, Iterable, Optional

from channel.wechat_group.protocol import (
    SidecarCommand,
    SidecarCommandType,
    build_send_text_command,
    parse_sidecar_event,
)
from common.log import logger
from config import conf


MEMORY_CARD_FILE_SUFFIX = ".memory-card.json"


def get_wechat_group_sidecar_memory_prefix() -> str:
    configured_path = conf().get("wechat_group_sidecar_memory_path")
    memory_prefix = configured_path or os.path.join("~", ".lightagent", "wechat_group")
    return os.path.abspath(os.path.expanduser(os.fspath(memory_prefix)))


def get_wechat_group_sidecar_memory_path() -> str:
    return get_wechat_group_sidecar_memory_prefix()


def get_wechat_group_memory_card_file_path() -> str:
    memory_prefix = get_wechat_group_sidecar_memory_prefix()
    if memory_prefix.endswith(MEMORY_CARD_FILE_SUFFIX):
        return memory_prefix
    return memory_prefix + MEMORY_CARD_FILE_SUFFIX


class WechatGroupClient:
    STOP_TIMEOUT_SECONDS = 5
    TERMINATE_TIMEOUT_SECONDS = 3
    KILL_TIMEOUT_SECONDS = 3

    def __init__(self, event_handler: Optional[Callable] = None):
        self.event_handler = event_handler
        self.process = None
        self._reader_thread = None
        self._stderr_thread = None
        self._last_error = ""
        self._lock = threading.RLock()

    def start(self):
        with self._lock:
            self._last_error = ""
            if self.process and self.process.poll() is None:
                return
            self.process = None
            command = self._build_command()
            logger.info("[wechat_group] starting sidecar: {}".format(" ".join(command)))
            try:
                self.process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    cwd=self._sidecar_dir(),
                )
            except Exception as e:
                self._last_error = str(e)
                raise
            self._reader_thread = threading.Thread(
                target=self._read_loop,
                args=(self.process.stdout,),
                daemon=True,
            )
            self._reader_thread.start()
            self._stderr_thread = threading.Thread(
                target=self._read_stderr_loop,
                args=(self.process.stderr,),
                daemon=True,
            )
            self._stderr_thread.start()

    def stop(self):
        with self._lock:
            process = self.process
            if process is None:
                return
            if process.poll() is None:
                try:
                    self.send_command(SidecarCommand(SidecarCommandType.STOP))
                except Exception as e:
                    logger.warning(
                        "[wechat_group] failed to send sidecar stop command: {}".format(e)
                    )
                self._wait_for_process_exit(process)
            if self.process is process:
                self.process = None

    def _wait_for_process_exit(self, process):
        try:
            process.wait(timeout=self.STOP_TIMEOUT_SECONDS)
            return
        except subprocess.TimeoutExpired:
            logger.warning("[wechat_group] sidecar stop timed out, terminating process")

        process.terminate()
        try:
            process.wait(timeout=self.TERMINATE_TIMEOUT_SECONDS)
            return
        except subprocess.TimeoutExpired:
            logger.warning("[wechat_group] sidecar terminate timed out, killing process")

        process.kill()
        process.wait(timeout=self.KILL_TIMEOUT_SECONDS)

    def force_rescan(self):
        with self._lock:
            self.stop()
            memory_file_path = get_wechat_group_memory_card_file_path()
            try:
                os.remove(memory_file_path)
            except FileNotFoundError:
                pass
            except OSError as e:
                try:
                    self.start()
                except Exception as restart_error:
                    raise RuntimeError(
                        "failed to remove WeChat group login cache '{}': {}; "
                        "failed to restart sidecar: {}".format(
                            memory_file_path,
                            e,
                            restart_error,
                        )
                    ) from e
                raise RuntimeError(
                    "failed to remove WeChat group login cache '{}': {}; "
                    "the previous sidecar connection was restarted".format(
                        memory_file_path,
                        e,
                    )
                ) from e
            self.start()

    def list_rooms(self):
        self.send_command(SidecarCommand(SidecarCommandType.LIST_ROOMS))

    def list_room_members(self, room_id: str, request_id: str = "", query: str = ""):
        payload = {"room_id": room_id}
        if request_id:
            payload["request_id"] = request_id
        if query:
            payload["query"] = query
        self.send_command(SidecarCommand(SidecarCommandType.LIST_ROOM_MEMBERS, payload))

    def send_text(self, room_id: str, text: str, mention_ids=None):
        cooldown_minutes = conf().get("wechat_group_alias_sync_cooldown_minutes", 1)
        self.send_command(build_send_text_command(room_id, text, mention_ids, int(cooldown_minutes or 1)))

    def send_file(self, room_id: str, path: str):
        self.send_command(SidecarCommand(SidecarCommandType.SEND_FILE, {
            "room_id": room_id,
            "path": path,
        }))

    def send_image(self, room_id: str, path: str):
        self.send_command(SidecarCommand(SidecarCommandType.SEND_IMAGE, {
            "room_id": room_id,
            "path": path,
        }))

    def send_audio(self, room_id: str, path: str):
        self.send_command(SidecarCommand(SidecarCommandType.SEND_AUDIO, {
            "room_id": room_id,
            "path": path,
        }))

    def send_command(self, command: SidecarCommand):
        line = json.dumps(command.to_json(), ensure_ascii=False)
        with self._lock:
            process = self.process
            stdin = process.stdin if process is not None else None
            if stdin is None:
                raise RuntimeError("wechat group sidecar is not started")
            stdin.write(line + "\n")
            stdin.flush()

    def poll_error(self) -> str:
        if self._last_error:
            return self._last_error
        if self.process and self.process.poll() is not None:
            return "wechat group sidecar exited with code {}".format(self.process.returncode)
        return ""

    def _read_loop(self, stdout):
        if not stdout:
            return
        for line in stdout:
            try:
                event = parse_sidecar_event(json.loads(line))
                if self.event_handler:
                    self.event_handler(event)
            except Exception as e:
                logger.warning("[wechat_group] failed to parse sidecar line: {}, line={}".format(e, line[:200]))

    def _read_stderr_loop(self, stderr):
        if not stderr:
            return
        for line in stderr:
            line = line.strip()
            if line:
                logger.warning("[wechat_group] sidecar stderr: {}".format(line))

    def _build_command(self) -> Iterable[str]:
        node = conf().get("wechat_group_sidecar_node") or "node"
        return [node, "wechaty-sidecar.mjs", self._build_sidecar_config_arg()]

    def _build_sidecar_config_arg(self) -> str:
        data_dir = get_wechat_group_sidecar_memory_prefix()
        media_dir = conf().get("wechat_group_media_dir") or os.path.join(data_dir, "media")
        config = {
            "puppet": conf().get("wechat_group_puppet") or "wechaty-puppet-wechat4u",
            "memory_path": data_dir,
            "media_dir": media_dir,
            "room_ids": conf().get("wechat_group_room_ids", []),
            "room_names": conf().get("wechat_group_names", []),
            "alias_sync_cooldown_minutes": conf().get("wechat_group_alias_sync_cooldown_minutes", 1),
        }
        return json.dumps(config, ensure_ascii=False)

    @staticmethod
    def _sidecar_dir() -> str:
        return os.path.join(os.path.dirname(__file__), "sidecar")
