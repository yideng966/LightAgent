"""Short-lived, prompt-safe tool continuation capsules for WeChat groups."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from typing import Any, Dict, Iterable, Optional

from channel.wechat_group.wechat_group_context import sanitize_wechat_group_prompt_text


SAFE_CONTINUATION_TOOLS = frozenset({
    "web_fetch",
    "browser",
    "wechat_group_memory_search",
    "wechat_group_profile_get",
    "wechat_group_sticker_search",
    "wechat_group_report",
})


def _default_path() -> str:
    root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(
        os.path.expanduser("~"), ".lightagent"
    )
    return os.path.join(os.path.expanduser(root), "wechat_group", "continuations.db")


class WechatGroupContinuationStore:
    def __init__(self, db_path: str = ""):
        self.db_path = str(db_path or _default_path())
        self._lock = threading.Lock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wechat_group_continuations (
                    owner_session_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    stable_room_id TEXT NOT NULL DEFAULT '',
                    stable_member_id TEXT NOT NULL DEFAULT '',
                    request_id TEXT NOT NULL DEFAULT '',
                    tool_name TEXT NOT NULL,
                    argument_summary TEXT NOT NULL DEFAULT '',
                    result_summary TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'success',
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    PRIMARY KEY (owner_session_id, thread_id)
                )
                """
            )
            conn.commit()

    def save_from_messages(
        self,
        owner_session_id: str,
        thread_id: str,
        messages: Iterable[Dict[str, Any]],
        stable_room_id: str,
        stable_member_id: str,
        request_id: str = "",
        ttl_seconds: int = 600,
    ) -> bool:
        capsule = build_safe_continuation_capsule(messages)
        return self.save_capsule(
            owner_session_id,
            thread_id,
            capsule,
            stable_room_id=stable_room_id,
            stable_member_id=stable_member_id,
            request_id=request_id,
            ttl_seconds=ttl_seconds,
        )

    def save_capsule(
        self,
        owner_session_id: str,
        thread_id: str,
        capsule: Optional[Dict[str, str]],
        stable_room_id: str,
        stable_member_id: str,
        request_id: str = "",
        ttl_seconds: int = 600,
    ) -> bool:
        if not capsule or not owner_session_id or not thread_id:
            return False
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO wechat_group_continuations (
                        owner_session_id, thread_id, stable_room_id,
                        stable_member_id, request_id, tool_name,
                        argument_summary, result_summary, status,
                        created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(owner_session_id),
                        str(thread_id),
                        str(stable_room_id or ""),
                        str(stable_member_id or ""),
                        str(request_id or ""),
                        capsule["tool_name"],
                        capsule["argument_summary"],
                        capsule["result_summary"],
                        capsule["status"],
                        now,
                        now + max(int(ttl_seconds or 600), 60),
                    ),
                )
        return True

    def get_prompt_block(
        self,
        owner_session_id: str,
        thread_id: str,
        stable_room_id: str,
        stable_member_id: str,
    ) -> str:
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT tool_name, argument_summary, result_summary, status
                FROM wechat_group_continuations
                WHERE owner_session_id = ? AND thread_id = ?
                  AND stable_room_id = ? AND stable_member_id = ?
                  AND expires_at >= ?
                """,
                (
                    str(owner_session_id or ""),
                    str(thread_id or ""),
                    str(stable_room_id or ""),
                    str(stable_member_id or ""),
                    now,
                ),
            ).fetchone()
        if not row:
            return ""
        return (
            '<wechat-group-continuation untrusted="true">\n'
            "tool: {}\narguments: {}\nstatus: {}\nresult: {}\n"
            "</wechat-group-continuation>"
        ).format(row[0], row[1] or "-", row[3] or "unknown", row[2] or "-")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn


def build_safe_continuation_capsule(
    messages: Iterable[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    calls: Dict[str, Dict[str, Any]] = {}
    candidates = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_name = str(block.get("name") or "").strip()
                arguments = block.get("input") or {}
                if tool_name in SAFE_CONTINUATION_TOOLS and _is_safe_read_call(
                    tool_name,
                    arguments,
                ):
                    calls[str(block.get("id") or "")] = {
                        "tool_name": tool_name,
                        "arguments": arguments,
                    }
            elif block.get("type") == "tool_result":
                call = calls.get(str(block.get("tool_use_id") or ""))
                if call:
                    candidates.append((call, block.get("content"), block.get("is_error")))
        if role == "tool":
            tool_name = str(message.get("name") or "").strip()
            arguments = message.get("arguments") or {}
            if tool_name in SAFE_CONTINUATION_TOOLS and _is_safe_read_call(
                tool_name,
                arguments,
            ):
                candidates.append(({
                    "tool_name": tool_name,
                    "arguments": arguments,
                }, content, False))
    if not candidates:
        return None
    call, result, is_error = candidates[-1]
    try:
        arguments = json.dumps(call.get("arguments") or {}, ensure_ascii=False)
    except Exception:
        arguments = str(call.get("arguments") or "")
    if isinstance(result, (dict, list)):
        try:
            result = json.dumps(result, ensure_ascii=False)
        except Exception:
            result = str(result)
    return {
        "tool_name": str(call.get("tool_name") or ""),
        "argument_summary": sanitize_wechat_group_prompt_text(arguments, 300),
        "result_summary": sanitize_wechat_group_prompt_text(result, 800),
        "status": "error" if is_error else "success",
    }


def _is_safe_read_call(tool_name: str, arguments: Any) -> bool:
    params = arguments if isinstance(arguments, dict) else {}
    if tool_name == "browser":
        return str(params.get("action") or "").strip() in {
            "snapshot",
            "get_text",
        }
    if tool_name == "wechat_group_report":
        return str(params.get("action") or "status").strip() == "status"
    return True
