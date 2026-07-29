"""
Conversation history persistence using SQLite.

Design:
- sessions table: per-session metadata (channel_type, last_active, msg_count)
- messages table: individual messages stored as JSON, append-only
- Pruning: age-based only (sessions not updated within N days are deleted)
- Thread-safe via a single in-process lock

Storage path: ~/lightagent/sessions/conversations.db
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.log import logger


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id        TEXT    PRIMARY KEY,
    channel_type      TEXT    NOT NULL DEFAULT '',
    title             TEXT    NOT NULL DEFAULT '',
    context_start_seq INTEGER NOT NULL DEFAULT 0,
    created_at        INTEGER NOT NULL,
    last_active       INTEGER NOT NULL,
    msg_count         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT    NOT NULL,
    thread_id    TEXT    NOT NULL DEFAULT '',
    seq          INTEGER NOT NULL,
    role         TEXT    NOT NULL,
    content      TEXT    NOT NULL,
    created_at   INTEGER NOT NULL,
    extras       TEXT    NOT NULL DEFAULT '',
    UNIQUE (session_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages (session_id, seq);

CREATE TABLE IF NOT EXISTS conversation_threads (
    session_id       TEXT    NOT NULL,
    thread_id        TEXT    NOT NULL,
    channel_type     TEXT    NOT NULL DEFAULT '',
    stable_room_id   TEXT    NOT NULL DEFAULT '',
    stable_member_id TEXT    NOT NULL DEFAULT '',
    status           TEXT    NOT NULL DEFAULT 'active',
    root_message_id  TEXT    NOT NULL DEFAULT '',
    last_message_id  TEXT    NOT NULL DEFAULT '',
    created_at       INTEGER NOT NULL,
    last_active      INTEGER NOT NULL,
    expires_at       INTEGER NOT NULL DEFAULT 0,
    metadata         TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (session_id, thread_id)
);

CREATE INDEX IF NOT EXISTS idx_conversation_threads_active
    ON conversation_threads (session_id, status, last_active DESC);

CREATE INDEX IF NOT EXISTS idx_sessions_last_active
    ON sessions (last_active);
"""

# Migration: add channel_type column to existing databases that predate it.
_MIGRATION_ADD_CHANNEL_TYPE = """
ALTER TABLE sessions ADD COLUMN channel_type TEXT NOT NULL DEFAULT '';
"""

_MIGRATION_ADD_TITLE = """
ALTER TABLE sessions ADD COLUMN title TEXT NOT NULL DEFAULT '';
"""

_MIGRATION_ADD_CONTEXT_START_SEQ = """
ALTER TABLE sessions ADD COLUMN context_start_seq INTEGER NOT NULL DEFAULT 0;
"""

# Generic JSON sidecar for per-message attachments (TTS audio URL, future use).
# Always optional — readers must tolerate missing column / empty / invalid JSON.
_MIGRATION_ADD_MSG_EXTRAS = """
ALTER TABLE messages ADD COLUMN extras TEXT NOT NULL DEFAULT '';
"""

_MIGRATION_ADD_MSG_THREAD_ID = """
ALTER TABLE messages ADD COLUMN thread_id TEXT NOT NULL DEFAULT '';
"""

DEFAULT_MAX_AGE_DAYS: int = 30


def _is_visible_user_message(content: Any) -> bool:
    """
    Return True when a user-role message represents actual user input
    (not an internal tool_result injected by the agent loop).
    """
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get("type") == "text"
            for b in content
        )
    return False


def _extract_display_text(content: Any) -> str:
    """
    Extract the human-readable text portion from a message content value.
    Returns an empty string for tool_use / tool_result blocks.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p).strip()
    return ""


def _message_history_visibility(raw_extras: Any) -> str:
    extras = _parse_message_extras(raw_extras)
    if not isinstance(extras, dict):
        return ""
    return str(extras.get("history_visibility") or "").strip()


def _parse_message_extras(raw_extras: Any) -> Dict[str, Any]:
    if isinstance(raw_extras, dict):
        return raw_extras
    try:
        extras = json.loads(raw_extras) if raw_extras else {}
    except Exception:
        extras = {}
    return extras if isinstance(extras, dict) else {}


def _message_delivery_state(raw_extras: Any) -> str:
    return str(
        _parse_message_extras(raw_extras).get("delivery_state") or ""
    ).strip()


def _pending_delivery_matches(raw_extras: Any, request_id: str) -> bool:
    extras = _parse_message_extras(raw_extras)
    return bool(
        extras.get("delivery_state") == "pending"
        and str(extras.get("delivery_request_id") or "") == str(request_id or "")
    )


# Internal markers written into the session for the agent's own bookkeeping
# (scheduler injection / self-evolution undo). They must stay in the stored
# content (the LLM reads them, e.g. to find a backup_id for undo) but should
# never be shown verbatim to the user in the chat history UI.
_SCHEDULED_DISPLAY_MARKERS = ("[SCHEDULED]", "Scheduled task")
_EVOLUTION_DISPLAY_MARKER = "[EVOLUTION]"


def _is_internal_user_marker(text: str) -> bool:
    """True if a user-turn text is an internal injection marker (hide from UI)."""
    t = (text or "").lstrip()
    return any(t.startswith(m) for m in _SCHEDULED_DISPLAY_MARKERS)


def _is_evolution_text(text: str) -> bool:
    """True if assistant text is a self-evolution summary (before cleaning)."""
    return (text or "").lstrip().startswith(_EVOLUTION_DISPLAY_MARKER)


def _clean_display_text(text: str) -> str:
    """Strip internal markers from assistant text for user-facing display.

    Removes a leading ``[EVOLUTION]`` tag and a trailing ``(backup_id: ...)``
    undo hint. The raw stored message is untouched, so undo + LLM context still
    work; only the rendered chat bubble is cleaned.
    """
    if not text:
        return text
    cleaned = text
    stripped = cleaned.lstrip()
    if stripped.startswith(_EVOLUTION_DISPLAY_MARKER):
        cleaned = stripped[len(_EVOLUTION_DISPLAY_MARKER):].lstrip()
    # Drop a trailing backup_id undo hint line, e.g.
    #   "(backup_id: 20260607-...; to undo, restore this backup)"
    cleaned = re.sub(
        r"\n*\(backup_id:[^\)]*\)\s*$",
        "",
        cleaned,
    ).rstrip()
    return cleaned


def _extract_tool_calls(content: Any) -> List[Dict[str, Any]]:
    """
    Extract tool_use blocks from an assistant message content.
    Returns a list of {name, arguments} dicts (result filled in later).
    """
    if not isinstance(content, list):
        return []
    return [
        {"id": b.get("id", ""), "name": b.get("name", ""), "arguments": b.get("input", {})}
        for b in content
        if isinstance(b, dict) and b.get("type") == "tool_use"
    ]


def _extract_tool_results(content: Any) -> Dict[str, dict]:
    """
    Extract tool_result blocks from a user message, keyed by tool_use_id.
    Values are {"result": str, "is_error": bool}.
    """
    if not isinstance(content, list):
        return {}
    results = {}
    for b in content:
        if not isinstance(b, dict) or b.get("type") != "tool_result":
            continue
        tool_id = b.get("tool_use_id", "")
        result_content = b.get("content", "")
        if isinstance(result_content, list):
            result_content = "\n".join(
                rb.get("text", "") for rb in result_content
                if isinstance(rb, dict) and rb.get("type") == "text"
            )
        results[tool_id] = {"result": str(result_content), "is_error": bool(b.get("is_error", False))}
    return results


def _group_into_display_turns(
    rows: List[tuple],
    include_thinking: bool = True,
) -> List[Dict[str, Any]]:
    """
    Convert raw (role, content_json, created_at) DB rows into display turns.

    One display turn = one visible user message  +  one merged assistant reply.
    All intermediate assistant messages (those carrying tool_use) and the final
    assistant text reply produced for the same user query are collapsed into a
    single assistant turn, exactly matching the live SSE rendering where tools
    and the final answer appear inside the same bubble.

    Grouping rules:
    - A visible user message starts a new group.
    - tool_result user messages are internal; their content is attached to the
      matching tool_use entry via tool_use_id and they never become own turns.
    - All assistant messages within a group are merged:
        * tool_use blocks → tool_calls list (result filled from tool_results)
        * text blocks → last non-empty text becomes the display content
    """
    # ------------------------------------------------------------------ #
    # Pass 1: split rows into groups, each starting with a visible user msg
    # ------------------------------------------------------------------ #
    # group = (user_row | None, [subsequent_rows])
    # user_row: (content, created_at)
    groups: List[tuple] = []
    cur_user: Optional[tuple] = None
    cur_rest: List[tuple] = []
    started = False

    for role, raw_content, created_at, raw_extras in rows:
        try:
            content = json.loads(raw_content)
        except Exception:
            content = raw_content
        try:
            extras = json.loads(raw_extras) if raw_extras else {}
            if not isinstance(extras, dict):
                extras = {}
        except Exception:
            extras = {}

        if role == "user" and _is_visible_user_message(content):
            if started:
                groups.append((cur_user, cur_rest))
            cur_user = (content, created_at, extras)
            cur_rest = []
            started = True
        else:
            cur_rest.append((role, content, created_at, extras))

    if started:
        groups.append((cur_user, cur_rest))

    # ------------------------------------------------------------------ #
    # Pass 2: build display turns from each group
    # ------------------------------------------------------------------ #
    turns: List[Dict[str, Any]] = []

    for user_row, rest in groups:
        # User turn
        if user_row:
            content, created_at, _u_extras = user_row
            text = _extract_display_text(content)
            # Hide internal injection markers (scheduler / self-evolution) so the
            # user never sees a synthetic "[SCHEDULED] self-evolution" bubble;
            # the assistant reply that follows is still rendered.
            if text and not _is_internal_user_marker(text):
                turns.append({"role": "user", "content": text, "created_at": created_at})

        # Build an ordered list of steps preserving the original sequence:
        #   thinking → content → tool_call → content → ...
        steps: List[Dict[str, Any]] = []
        tool_results: Dict[str, str] = {}
        final_text = ""
        final_ts: Optional[int] = None
        merged_extras: Dict[str, Any] = {}

        for role, content, created_at, extras in rest:
            if role == "assistant" and isinstance(extras, dict):
                merged_extras.update(extras)
            if role == "user":
                tool_results.update(_extract_tool_results(content))
            elif role == "assistant":
                # Walk content blocks in order to preserve interleaving
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "thinking":
                            if not include_thinking:
                                continue
                            txt = block.get("thinking", "").strip()
                            if txt:
                                steps.append({"type": "thinking", "content": txt})
                        elif btype == "text":
                            txt = block.get("text", "").strip()
                            if txt:
                                steps.append({"type": "content", "content": txt})
                                final_text = txt
                        elif btype == "tool_use":
                            steps.append({
                                "type": "tool",
                                "id": block.get("id", ""),
                                "name": block.get("name", ""),
                                "arguments": block.get("input", {}),
                            })
                elif isinstance(content, str) and content.strip():
                    steps.append({"type": "content", "content": content.strip()})
                    final_text = content.strip()
                final_ts = created_at

        # Attach tool results to tool steps
        for step in steps:
            if step["type"] == "tool":
                tr = tool_results.get(step.get("id", ""), {})
                if not isinstance(tr, dict):
                    tr = {"result": tr}
                step["result"] = tr.get("result", "")
                step["is_error"] = tr.get("is_error", False)

        # Detect a self-evolution bubble BEFORE cleaning the marker away, so the
        # UI can flag it even though the visible text stays clean.
        is_evolution = _is_evolution_text(final_text)

        # Clean internal markers from the user-facing assistant text. Applies to
        # both the final content and the mirrored content step so the rendered
        # bubble shows clean text while the stored message keeps the markers.
        final_text = _clean_display_text(final_text)
        for step in steps:
            if step.get("type") == "content":
                step["content"] = _clean_display_text(step.get("content", ""))

        if steps or final_text:
            turn = {
                "role": "assistant",
                "content": final_text,
                "steps": steps,
                "created_at": final_ts or (user_row[1] if user_row else 0),
            }
            if is_evolution:
                turn["kind"] = "evolution"
            if merged_extras:
                turn["extras"] = merged_extras
            turns.append(turn)

    return turns


class ConversationStore:
    """
    SQLite-backed store for per-session conversation history.

    Usage:
        store = ConversationStore(db_path)
        store.append_messages("user_123", new_messages, channel_type="feishu")
        msgs = store.load_messages("user_123", max_turns=30)
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._lock = threading.RLock()  # Use RLock to allow reentrant locking
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_messages(
        self,
        session_id: str,
        max_turns: int = 30,
        include_observe_only: bool = False,
        thread_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Load the most recent messages for a session, for injection into the LLM.

        ALL message types (user text, assistant tool_use, tool_result) are returned
        in their original JSON form so the LLM can reconstruct the full context.

        max_turns is a *visible-turn* count: we count only user messages whose
        content is actual user text (not tool_result blocks).  This prevents
        tool-heavy sessions from exhausting the turn budget prematurely.

        Args:
            session_id: Unique session identifier.
            max_turns: Maximum number of visible user-assistant turns to keep.
            include_observe_only: Include audit-only turns that must not be
                restored into normal model context. Defaults to False.
            thread_id: Optional logical conversation thread. ``None`` keeps
                the legacy session-wide behavior; a string selects only that
                thread, including the empty legacy thread when ``""``.

        Returns:
            Chronologically ordered list of message dicts (role, content).
        """
        with self._lock:
            conn = self._connect()
            try:
                # Respect context_start_seq: only load messages at or after the boundary
                ctx_row = conn.execute(
                    "SELECT context_start_seq FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                ctx_start = ctx_row[0] if ctx_row else 0

                if thread_id is None:
                    rows = conn.execute(
                        """
                        SELECT seq, role, content, extras
                        FROM messages
                        WHERE session_id = ? AND seq >= ?
                        ORDER BY seq DESC
                        """,
                        (session_id, ctx_start),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT seq, role, content, extras
                        FROM messages
                        WHERE session_id = ? AND seq >= ? AND thread_id = ?
                        ORDER BY seq DESC
                        """,
                        (session_id, ctx_start, str(thread_id or "")),
                    ).fetchall()
            finally:
                conn.close()

        if not rows:
            return []

        if not include_observe_only:
            rows = [
                row for row in rows
                if _message_history_visibility(row[3]) != "observe_only"
            ]
        rows = [
            row for row in rows
            if _message_delivery_state(row[3]) != "pending"
        ]

        visible_turn_seqs: List[int] = []
        for seq, role, raw_content, _extras in rows:
            if role != "user":
                continue
            try:
                content = json.loads(raw_content)
            except Exception:
                content = raw_content
            if _is_visible_user_message(content):
                visible_turn_seqs.append(seq)

        if len(visible_turn_seqs) <= max_turns:
            cutoff_seq = None
        else:
            cutoff_seq = visible_turn_seqs[max_turns - 1]

        result = []
        for seq, role, raw_content, _extras in reversed(rows):
            if cutoff_seq is not None and seq < cutoff_seq:
                continue
            try:
                content = json.loads(raw_content)
            except Exception:
                content = raw_content
            # Strip thinking blocks — they are stored for UI display only
            if role == "assistant" and isinstance(content, list):
                content = [b for b in content if b.get("type") != "thinking"]
            result.append({"role": role, "content": content})
        return result

    def get_session_channel_type(self, session_id: str) -> str:
        """返回持久化会话的来源渠道；会话不存在时返回空字符串。"""
        if not session_id:
            return ""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT channel_type FROM sessions WHERE session_id = ?",
                    (str(session_id),),
                ).fetchone()
            finally:
                conn.close()
        return str(row[0] or "") if row else ""

    def append_messages(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        channel_type: str = "",
        thread_id: str = "",
    ) -> None:
        """
        Append new messages to a session's history.

        Seq numbers continue from the session's current maximum, so
        concurrent callers on distinct sessions never collide.

        Args:
            session_id: Unique session identifier.
            messages: List of message dicts to append.
            channel_type: Source channel (e.g. "feishu", "web", "wechat").
                          Only written on session creation; ignored on update.
            thread_id: Optional logical thread within the owner session.
        """
        if not messages:
            return

        now = int(time.time())
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    # INSERT OR IGNORE creates the row on first visit;
                    # the UPDATE always refreshes last_active.
                    # Avoids ON CONFLICT...DO UPDATE (requires SQLite >= 3.24).
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO sessions
                            (session_id, channel_type, created_at, last_active, msg_count)
                        VALUES (?, ?, ?, ?, 0)
                        """,
                        (session_id, channel_type, now, now),
                    )
                    conn.execute(
                        "UPDATE sessions SET last_active = ? WHERE session_id = ?",
                        (now, session_id),
                    )

                    # Determine starting seq for the new batch.
                    row = conn.execute(
                        "SELECT COALESCE(MAX(seq), -1) FROM messages WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()
                    next_seq = row[0] + 1

                    for msg in messages:
                        role = msg.get("role", "")
                        content = json.dumps(
                            msg.get("content", ""), ensure_ascii=False
                        )
                        extras_obj = msg.get("extras") or {}
                        extras = json.dumps(extras_obj, ensure_ascii=False) if extras_obj else ""
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO messages
                                (session_id, thread_id, seq, role, content, created_at, extras)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                session_id,
                                str(thread_id or ""),
                                next_seq,
                                role,
                                content,
                                now,
                                extras,
                            ),
                        )
                        next_seq += 1

                    conn.execute(
                        """
                        UPDATE sessions
                        SET msg_count = (
                            SELECT COUNT(*) FROM messages WHERE session_id = ?
                        )
                        WHERE session_id = ?
                        """,
                        (session_id, session_id),
                    )

                    # Auto-generate title from the first visible user message
                    cur_title = conn.execute(
                        "SELECT title FROM sessions WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()
                    if cur_title and not cur_title[0]:
                        for msg in messages:
                            if msg.get("role") == "user":
                                content = msg.get("content", "")
                                text = _extract_display_text(content)
                                if text:
                                    title = text[:50].split("\n")[0]
                                    conn.execute(
                                        "UPDATE sessions SET title = ? WHERE session_id = ?",
                                        (title, session_id),
                                    )
                                    break
            finally:
                conn.close()

    def create_thread(
        self,
        session_id: str,
        thread_id: str,
        channel_type: str = "wechat_group",
        stable_room_id: str = "",
        stable_member_id: str = "",
        root_message_id: str = "",
        ttl_seconds: int = 900,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create and activate a non-destructive logical conversation thread."""
        session_key = str(session_id or "").strip()
        thread_key = str(thread_id or "").strip()
        if not session_key or not thread_key:
            raise ValueError("session_id and thread_id are required")
        now = int(time.time())
        ttl = max(int(ttl_seconds or 0), 0)
        expires_at = now + ttl if ttl else 0
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False) if metadata else ""
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "UPDATE conversation_threads SET status = 'closed' "
                        "WHERE session_id = ? AND status = 'active' AND thread_id <> ?",
                        (session_key, thread_key),
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO conversation_threads (
                            session_id, thread_id, channel_type, stable_room_id,
                            stable_member_id, status, root_message_id,
                            last_message_id, created_at, last_active, expires_at,
                            metadata
                        ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session_key,
                            thread_key,
                            str(channel_type or ""),
                            str(stable_room_id or ""),
                            str(stable_member_id or ""),
                            str(root_message_id or ""),
                            str(root_message_id or ""),
                            now,
                            now,
                            expires_at,
                            metadata_json,
                        ),
                    )
                    conn.execute(
                        """
                        UPDATE conversation_threads
                        SET status = 'active', last_active = ?, expires_at = ?,
                            last_message_id = CASE WHEN ? <> '' THEN ? ELSE last_message_id END
                        WHERE session_id = ? AND thread_id = ?
                        """,
                        (
                            now,
                            expires_at,
                            str(root_message_id or ""),
                            str(root_message_id or ""),
                            session_key,
                            thread_key,
                        ),
                    )
            finally:
                conn.close()
        return self.get_thread(session_key, thread_key) or {}

    def touch_thread(
        self,
        session_id: str,
        thread_id: str,
        message_id: str = "",
        ttl_seconds: int = 900,
    ) -> bool:
        """Refresh one thread without changing any other thread's history."""
        now = int(time.time())
        ttl = max(int(ttl_seconds or 0), 0)
        expires_at = now + ttl if ttl else 0
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    cur = conn.execute(
                        """
                        UPDATE conversation_threads
                        SET status = 'active', last_active = ?, expires_at = ?,
                            last_message_id = CASE WHEN ? <> '' THEN ? ELSE last_message_id END
                        WHERE session_id = ? AND thread_id = ?
                        """,
                        (
                            now,
                            expires_at,
                            str(message_id or ""),
                            str(message_id or ""),
                            str(session_id or ""),
                            str(thread_id or ""),
                        ),
                    )
                    return cur.rowcount > 0
            finally:
                conn.close()

    def get_active_thread(
        self,
        session_id: str,
        ttl_seconds: int = 900,
    ) -> Optional[Dict[str, Any]]:
        """Return the newest unexpired active thread for an owner session."""
        now = int(time.time())
        cutoff = now - max(int(ttl_seconds or 0), 0)
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT session_id, thread_id, channel_type, stable_room_id,
                           stable_member_id, status, root_message_id,
                           last_message_id, created_at, last_active, expires_at,
                           metadata
                    FROM conversation_threads
                    WHERE session_id = ? AND status = 'active'
                      AND last_active >= ?
                      AND (expires_at = 0 OR expires_at >= ?)
                    ORDER BY last_active DESC, created_at DESC
                    LIMIT 1
                    """,
                    (str(session_id or ""), cutoff, now),
                ).fetchone()
            finally:
                conn.close()
        return self._thread_row_to_dict(row)

    def get_thread(self, session_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT session_id, thread_id, channel_type, stable_room_id,
                           stable_member_id, status, root_message_id,
                           last_message_id, created_at, last_active, expires_at,
                           metadata
                    FROM conversation_threads
                    WHERE session_id = ? AND thread_id = ?
                    """,
                    (str(session_id or ""), str(thread_id or "")),
                ).fetchone()
            finally:
                conn.close()
        return self._thread_row_to_dict(row)

    def get_thread_source_event_ids(self, session_id: str, thread_id: str) -> List[str]:
        """Return room timeline event ids already represented in a thread."""
        if not session_id or not thread_id:
            return []
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT extras FROM messages
                    WHERE session_id = ? AND thread_id = ? AND extras <> ''
                    ORDER BY seq ASC
                    """,
                    (str(session_id), str(thread_id)),
                ).fetchall()
            finally:
                conn.close()
        result = []
        seen = set()
        for (raw,) in rows:
            extras = _parse_message_extras(raw)
            if extras.get("delivery_state") == "pending":
                continue
            event_id = str(
                extras.get("source_event_id") if isinstance(extras, dict) else ""
            ).strip()
            if event_id and event_id not in seen:
                seen.add(event_id)
                result.append(event_id)
        return result

    @staticmethod
    def _thread_row_to_dict(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        try:
            metadata = json.loads(row[11]) if row[11] else {}
        except Exception:
            metadata = {}
        return {
            "session_id": str(row[0] or ""),
            "thread_id": str(row[1] or ""),
            "channel_type": str(row[2] or ""),
            "stable_room_id": str(row[3] or ""),
            "stable_member_id": str(row[4] or ""),
            "status": str(row[5] or ""),
            "root_message_id": str(row[6] or ""),
            "last_message_id": str(row[7] or ""),
            "created_at": int(row[8] or 0),
            "last_active": int(row[9] or 0),
            "expires_at": int(row[10] or 0),
            "metadata": metadata if isinstance(metadata, dict) else {},
        }

    def clear_context(self, session_id: str) -> int:
        """
        Set the context boundary to after the current last message.
        Messages before this boundary are still stored but excluded from LLM context.

        Returns the new context_start_seq value.
        """
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    row = conn.execute(
                        "SELECT COALESCE(MAX(seq), -1) FROM messages WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()
                    new_start = row[0] + 1
                    conn.execute(
                        "UPDATE sessions SET context_start_seq = ? WHERE session_id = ?",
                        (new_start, session_id),
                    )
                    return new_start
            finally:
                conn.close()

    def get_context_start_seq(self, session_id: str) -> int:
        """Return the context_start_seq for a session (0 if not set)."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT context_start_seq FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    def get_latest_pair_seqs(self, session_id: str) -> Dict[str, Optional[int]]:
        """Return the seq numbers of the latest visible user message and the
        latest assistant message in a session.

        A "visible" user message is one whose content is real user text
        (not just a tool_result block), so tool-execution turns do not
        shadow the actual user query.

        Returns:
            Dict with keys ``user_seq`` and ``bot_seq``; either may be None
            when no matching message exists.
        """
        result: Dict[str, Optional[int]] = {"user_seq": None, "bot_seq": None}
        with self._lock:
            conn = self._connect()
            try:
                # Latest assistant message (cheap: single row by seq DESC).
                row = conn.execute(
                    "SELECT seq FROM messages "
                    "WHERE session_id = ? AND role = 'assistant' "
                    "ORDER BY seq DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
                if row:
                    result["bot_seq"] = int(row[0])

                # Latest visible user message: scan recent user rows and
                # skip pure tool_result entries.
                rows = conn.execute(
                    "SELECT seq, content FROM messages "
                    "WHERE session_id = ? AND role = 'user' "
                    "ORDER BY seq DESC LIMIT 20",
                    (session_id,),
                ).fetchall()
                for seq, content_raw in rows:
                    try:
                        content = json.loads(content_raw)
                    except Exception:
                        result["user_seq"] = int(seq)
                        break
                    if isinstance(content, list):
                        has_text = any(
                            isinstance(b, dict) and b.get("type") == "text"
                            for b in content
                        )
                        has_tool_result = any(
                            isinstance(b, dict) and b.get("type") == "tool_result"
                            for b in content
                        )
                        if has_text and not has_tool_result:
                            result["user_seq"] = int(seq)
                            break
                    else:
                        result["user_seq"] = int(seq)
                        break
            finally:
                conn.close()
        return result

    def clear_session(self, session_id: str) -> None:
        """Delete all messages and the session record for a given session_id."""
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "DELETE FROM messages WHERE session_id = ?", (session_id,)
                    )
                    conn.execute(
                        "DELETE FROM conversation_threads WHERE session_id = ?",
                        (session_id,),
                    )
                    conn.execute(
                        "DELETE FROM sessions WHERE session_id = ?", (session_id,)
                    )
            finally:
                conn.close()

    def delete_message_pair(self, session_id: str, user_seq: int, delete_user: bool = True, cascade: bool = False) -> int:
        """Delete a user message and/or its corresponding assistant reply.

        The assistant reply is identified as all messages between user_seq
        and the next visible user message (or end of session).

        Args:
            session_id: Session identifier.
            user_seq: The seq number of the user message.
            delete_user: If True (default), delete the user message too.
                        If False, only delete assistant reply (for regenerate scenarios).
            cascade: If True, also delete all subsequent turns after this one.
                    Used by edit-message which removes this turn and everything after.

        Returns:
            Number of message rows deleted.
        """
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    # Verify this is a user message
                    row = conn.execute(
                        "SELECT role FROM messages WHERE session_id = ? AND seq = ?",
                        (session_id, user_seq),
                    ).fetchone()
                    if not row or row[0] != "user":
                        return 0

                    if cascade:
                        # Delete from this message to end of session
                        start_seq = user_seq if delete_user else user_seq + 1
                        end_seq_row = conn.execute(
                            "SELECT MAX(seq) FROM messages WHERE session_id = ?",
                            (session_id,),
                        ).fetchone()
                        end_seq = (end_seq_row[0] or user_seq) + 1
                    else:
                        # Find the next visible user message seq (exclude tool_result)
                        # Use batched query to avoid loading too many rows at once
                        next_user_seq = None
                        batch_size = 100
                        offset = 0
                        while True:
                            batch = conn.execute(
                                """
                                SELECT seq, content FROM messages
                                WHERE session_id = ? AND seq > ? AND role = 'user'
                                ORDER BY seq ASC
                                LIMIT ? OFFSET ?
                                """,
                                (session_id, user_seq, batch_size, offset),
                            ).fetchall()
                            if not batch:
                                break
                            for seq, content in batch:
                                try:
                                    content_obj = json.loads(content)
                                except Exception:
                                    content_obj = content
                                if _is_visible_user_message(content_obj):
                                    next_user_seq = seq
                                    break
                            if next_user_seq is not None:
                                break
                            offset += batch_size

                        # Determine the end boundary for deletion
                        if next_user_seq is not None:
                            end_seq = next_user_seq
                        else:
                            end_seq_row = conn.execute(
                                "SELECT MAX(seq) FROM messages WHERE session_id = ?",
                                (session_id,),
                            ).fetchone()
                            end_seq = (end_seq_row[0] or user_seq) + 1

                        # Determine the start boundary for deletion
                        start_seq = user_seq if delete_user else user_seq + 1

                    # Delete messages from start_seq to end_seq (exclusive)
                    cur = conn.execute(
                        "DELETE FROM messages WHERE session_id = ? AND seq >= ? AND seq < ?",
                        (session_id, start_seq, end_seq),
                    )
                    deleted = cur.rowcount

                    # Update session msg_count
                    conn.execute(
                        """
                        UPDATE sessions
                        SET msg_count = (
                            SELECT COUNT(*) FROM messages WHERE session_id = ?
                        )
                        WHERE session_id = ?
                        """,
                        (session_id, session_id),
                    )

                    return deleted
            finally:
                conn.close()

    def prune_scheduled_messages(
        self,
        session_id: str,
        keep_last_n: int,
        markers: Optional[List[str]] = None,
    ) -> int:
        """
        Keep at most ``keep_last_n`` scheduler-injected user/assistant pairs in
        the session, deleting the older ones.

        A scheduler-injected pair is identified by a user message whose first
        text block starts with one of ``markers``; the immediately following
        assistant message (next seq) is treated as its paired output.

        Only scheduler-tagged messages are touched; regular user turns are
        never deleted. Safe to call repeatedly; no-op if nothing to prune.

        Args:
            session_id: Session to prune.
            keep_last_n: Maximum scheduler pairs to retain (must be >= 0).
            markers: Text prefixes that identify scheduler user messages.
                Defaults to ``["[SCHEDULED]", "Scheduled task"]`` so that
                pairs written by older versions are also recognised.

        Returns:
            Number of message rows deleted.
        """
        if keep_last_n < 0:
            keep_last_n = 0
        if markers is None:
            markers = ["[SCHEDULED]", "Scheduled task"]

        def _matches_marker(raw_content: str) -> bool:
            try:
                parsed = json.loads(raw_content)
            except Exception:
                parsed = raw_content
            text = _extract_display_text(parsed) if not isinstance(parsed, str) else parsed
            if not text:
                return False
            return any(text.startswith(m) for m in markers)

        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT seq, role, content
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY seq ASC
                    """,
                    (session_id,),
                ).fetchall()

                # Find scheduler pairs: each is (user_seq, assistant_seq?)
                pairs: List[tuple] = []  # list of (user_seq, assistant_seq_or_None)
                for idx, (seq, role, raw_content) in enumerate(rows):
                    if role != "user" or not _matches_marker(raw_content):
                        continue
                    assistant_seq = None
                    # Pair with the very next message if it's an assistant turn.
                    if idx + 1 < len(rows):
                        next_seq, next_role, _ = rows[idx + 1]
                        if next_role == "assistant":
                            assistant_seq = next_seq
                    pairs.append((seq, assistant_seq))

                if len(pairs) <= keep_last_n:
                    return 0

                to_delete_pairs = pairs[: len(pairs) - keep_last_n]
                seqs_to_delete: List[int] = []
                for user_seq, assistant_seq in to_delete_pairs:
                    seqs_to_delete.append(user_seq)
                    if assistant_seq is not None:
                        seqs_to_delete.append(assistant_seq)

                if not seqs_to_delete:
                    return 0

                placeholders = ",".join("?" * len(seqs_to_delete))
                with conn:
                    conn.execute(
                        f"DELETE FROM messages WHERE session_id = ? AND seq IN ({placeholders})",
                        (session_id, *seqs_to_delete),
                    )
                    conn.execute(
                        """
                        UPDATE sessions
                        SET msg_count = (
                            SELECT COUNT(*) FROM messages WHERE session_id = ?
                        )
                        WHERE session_id = ?
                        """,
                        (session_id, session_id),
                    )
                return len(seqs_to_delete)
            finally:
                conn.close()

    def cleanup_old_sessions(self, max_age_days: Optional[int] = None) -> int:
        """
        Delete sessions that have not been active within max_age_days.
        Web channel sessions are excluded — they are meant to be permanent.

        Args:
            max_age_days: Override the default retention period.

        Returns:
            Number of sessions deleted.
        """
        try:
            from config import conf
            max_age = max_age_days or conf().get(
                "conversation_max_age_days", DEFAULT_MAX_AGE_DAYS
            )
        except Exception:
            max_age = max_age_days or DEFAULT_MAX_AGE_DAYS

        cutoff = int(time.time()) - max_age * 86400
        deleted = 0

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    stale = conn.execute(
                        "SELECT session_id FROM sessions "
                        "WHERE last_active < ? AND channel_type != 'web'",
                        (cutoff,),
                    ).fetchall()
                    for (sid,) in stale:
                        conn.execute(
                            "DELETE FROM messages WHERE session_id = ?", (sid,)
                        )
                        conn.execute(
                            "DELETE FROM conversation_threads WHERE session_id = ?",
                            (sid,),
                        )
                        conn.execute(
                            "DELETE FROM sessions WHERE session_id = ?", (sid,)
                        )
                        deleted += 1
            finally:
                conn.close()

        if deleted:
            logger.info(f"[ConversationStore] Pruned {deleted} expired sessions")
        return deleted

    def attach_extras_to_last_assistant(
        self,
        session_id: str,
        extras: Dict[str, Any],
        thread_id: Optional[str] = None,
    ) -> Optional[int]:
        """
        Merge ``extras`` into the latest assistant message of a session.

        Used by post-processing (e.g. TTS) that needs to annotate an already
        persisted bot reply with attachments such as audio URLs.

        Returns the message seq that was updated, or ``None`` if no assistant
        message exists or the update could not be applied.
        """
        if not extras:
            return None
        with self._lock:
            conn = self._connect()
            try:
                if thread_id is None:
                    row = conn.execute(
                        """
                        SELECT seq, extras FROM messages
                        WHERE session_id = ? AND role = 'assistant'
                        ORDER BY seq DESC LIMIT 1
                        """,
                        (session_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT seq, extras FROM messages
                        WHERE session_id = ? AND thread_id = ? AND role = 'assistant'
                        ORDER BY seq DESC LIMIT 1
                        """,
                        (session_id, str(thread_id or "")),
                    ).fetchone()
                if not row:
                    return None
                seq, raw = row
                try:
                    cur = json.loads(raw) if raw else {}
                    if not isinstance(cur, dict):
                        cur = {}
                except Exception:
                    cur = {}
                cur.update(extras)
                conn.execute(
                    "UPDATE messages SET extras = ? WHERE session_id = ? AND seq = ?",
                    (json.dumps(cur, ensure_ascii=False), session_id, seq),
                )
                conn.commit()
                return seq
            except Exception as e:
                logger.warning(f"[ConversationStore] attach_extras failed: {e}")
                return None
            finally:
                conn.close()

    def confirm_thread_turn_delivery(
        self,
        session_id: str,
        thread_id: str,
        request_id: str,
        assistant_source_event_id: str = "",
        assistant_text: Optional[str] = None,
        thread_action: str = "",
        channel_type: str = "wechat_group",
        stable_room_id: str = "",
        stable_member_id: str = "",
        message_id: str = "",
        ttl_seconds: int = 900,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Commit one pending turn and its thread after send confirmation."""
        if not session_id or not thread_id or not request_id:
            return 0
        updated = 0
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT seq, role, extras FROM messages
                    WHERE session_id = ? AND thread_id = ? AND extras <> ''
                    ORDER BY seq ASC
                    """,
                    (str(session_id), str(thread_id)),
                ).fetchall()
                with conn:
                    for seq, role, raw_extras in rows:
                        extras = _parse_message_extras(raw_extras)
                        if (
                            extras.get("delivery_state") != "pending"
                            or str(extras.get("delivery_request_id") or "")
                            != str(request_id)
                        ):
                            continue
                        extras["delivery_state"] = "sent"
                        if role == "assistant" and assistant_source_event_id:
                            extras["source_event_id"] = str(
                                assistant_source_event_id
                            )
                        stored_content = None
                        if role == "assistant" and assistant_text is not None:
                            stored_content = json.dumps(
                                [{"type": "text", "text": str(assistant_text)}],
                                ensure_ascii=False,
                            )
                        if stored_content is None:
                            conn.execute(
                                """
                                UPDATE messages SET extras = ?
                                WHERE session_id = ? AND seq = ?
                                """,
                                (
                                    json.dumps(extras, ensure_ascii=False),
                                    str(session_id),
                                    int(seq),
                                ),
                            )
                        else:
                            conn.execute(
                                """
                                UPDATE messages SET content = ?, extras = ?
                                WHERE session_id = ? AND seq = ?
                                """,
                                (
                                    stored_content,
                                    json.dumps(extras, ensure_ascii=False),
                                    str(session_id),
                                    int(seq),
                                ),
                            )
                        updated += 1
                    if updated and thread_action in {"new_thread", "resume_thread"}:
                        now = int(time.time())
                        ttl = max(int(ttl_seconds or 0), 0)
                        expires_at = now + ttl if ttl else 0
                        metadata_json = (
                            json.dumps(metadata or {}, ensure_ascii=False)
                            if metadata
                            else ""
                        )
                        if thread_action == "new_thread":
                            conn.execute(
                                """
                                UPDATE conversation_threads SET status = 'closed'
                                WHERE session_id = ? AND status = 'active'
                                  AND thread_id <> ?
                                """,
                                (str(session_id), str(thread_id)),
                            )
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO conversation_threads (
                                session_id, thread_id, channel_type,
                                stable_room_id, stable_member_id, status,
                                root_message_id, last_message_id, created_at,
                                last_active, expires_at, metadata
                            ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(session_id),
                                str(thread_id),
                                str(channel_type or ""),
                                str(stable_room_id or ""),
                                str(stable_member_id or ""),
                                str(message_id or ""),
                                str(message_id or ""),
                                now,
                                now,
                                expires_at,
                                metadata_json,
                            ),
                        )
                        conn.execute(
                            """
                            UPDATE conversation_threads
                            SET status = 'active', last_active = ?, expires_at = ?,
                                last_message_id = CASE
                                    WHEN ? <> '' THEN ? ELSE last_message_id END
                            WHERE session_id = ? AND thread_id = ?
                            """,
                            (
                                now,
                                expires_at,
                                str(message_id or ""),
                                str(message_id or ""),
                                str(session_id),
                                str(thread_id),
                            ),
                        )
            finally:
                conn.close()
        return updated

    def discard_pending_thread_turn(
        self,
        session_id: str,
        thread_id: str,
        request_id: str,
    ) -> int:
        """Remove a turn that never reached the WeChat room."""
        if not session_id or not thread_id or not request_id:
            return 0
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT seq, extras FROM messages
                    WHERE session_id = ? AND thread_id = ? AND extras <> ''
                    """,
                    (str(session_id), str(thread_id)),
                ).fetchall()
                seqs = [
                    int(seq)
                    for seq, raw_extras in rows
                    if _pending_delivery_matches(raw_extras, request_id)
                ]
                if not seqs:
                    return 0
                placeholders = ",".join("?" * len(seqs))
                with conn:
                    conn.execute(
                        "DELETE FROM messages WHERE session_id = ? "
                        f"AND seq IN ({placeholders})",
                        (str(session_id), *seqs),
                    )
                    remaining = conn.execute(
                        "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                        (str(session_id),),
                    ).fetchone()[0]
                    if remaining:
                        conn.execute(
                            "UPDATE sessions SET msg_count = ? WHERE session_id = ?",
                            (int(remaining), str(session_id)),
                        )
                    else:
                        conn.execute(
                            "DELETE FROM sessions WHERE session_id = ?",
                            (str(session_id),),
                        )
                    thread_remaining = conn.execute(
                        """
                        SELECT COUNT(*) FROM messages
                        WHERE session_id = ? AND thread_id = ?
                        """,
                        (str(session_id), str(thread_id)),
                    ).fetchone()[0]
                    if not thread_remaining:
                        conn.execute(
                            """
                            DELETE FROM conversation_threads
                            WHERE session_id = ? AND thread_id = ?
                            """,
                            (str(session_id), str(thread_id)),
                        )
                return len(seqs)
            finally:
                conn.close()

    def load_history_page(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Load a page of conversation history for UI display, grouped into turns.

        Each "turn" maps to one of:
          - A user message (role="user", content=str)
          - An assistant message (role="assistant", content=str,
            tool_calls=[{name, arguments, result}] when tools were used)

        Internal tool_result user messages are merged into the preceding
        assistant entry's tool_calls list and never appear as standalone items.

        Pages are numbered from 1 (most recent).  Messages within a page are
        returned in chronological order.

        Returns:
            {
                "messages": [
                    {
                        "role": "user" | "assistant",
                        "content": str,
                        "tool_calls": [...],   # assistant only, may be []
                        "created_at": int,
                    },
                    ...
                ],
                "total": <visible turn count>,
                "page": <current page>,
                "page_size": <page_size>,
                "has_more": bool,
            }
        """
        page = max(1, page)
        with self._lock:
            conn = self._connect()
            try:
                ctx_row = conn.execute(
                    "SELECT context_start_seq FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                ctx_start = ctx_row[0] if ctx_row else 0

                # extras column is added by migration; tolerate older DBs that
                # might miss it by falling back to a NULL literal.
                try:
                    rows = conn.execute(
                        """
                        SELECT seq, role, content, created_at, extras
                        FROM messages
                        WHERE session_id = ?
                        ORDER BY seq ASC
                        """,
                        (session_id,),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = [
                        (seq, role, content, created_at, "")
                        for (seq, role, content, created_at) in conn.execute(
                            """
                            SELECT seq, role, content, created_at
                            FROM messages
                            WHERE session_id = ?
                            ORDER BY seq ASC
                            """,
                            (session_id,),
                        ).fetchall()
                    ]
            finally:
                conn.close()

        # Honour the current enable_thinking switch when building display turns
        # so that toggling it off hides previously-saved thinking blocks too.
        try:
            from config import conf
            include_thinking = bool(conf().get("enable_thinking", False))
        except Exception:
            include_thinking = False

        # Strip seq for display grouping, but record max seq per visible user group
        rows = [
            row
            for row in rows
            if _message_delivery_state(row[4]) != "pending"
        ]
        plain_rows = [
            (role, content, created_at, extras_raw)
            for _seq, role, content, created_at, extras_raw in rows
        ]
        visible = _group_into_display_turns(plain_rows, include_thinking=include_thinking)

        # Build a mapping: find the seq of each visible user message to annotate context boundary.
        # Walk through rows to find visible user message seqs in order.
        visible_user_seqs: List[int] = []
        for seq, role, raw_content, _ts, _extras in rows:
            if role != "user":
                continue
            try:
                content = json.loads(raw_content)
            except Exception:
                content = raw_content
            if _is_visible_user_message(content):
                visible_user_seqs.append(seq)

        # Each pair of display turns (user+assistant) corresponds to a visible user seq.
        # Mark which turns are before the context boundary.
        user_turn_idx = 0
        for turn in visible:
            if turn["role"] == "user" and user_turn_idx < len(visible_user_seqs):
                turn["_seq"] = visible_user_seqs[user_turn_idx]
                user_turn_idx += 1

        total = len(visible)
        offset = (page - 1) * page_size
        page_items = list(reversed(visible))[offset: offset + page_size]
        page_items = list(reversed(page_items))

        return {
            "messages": page_items,
            "context_start_seq": ctx_start,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": offset + page_size < total,
        }

    def list_sessions(
        self,
        channel_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        List sessions ordered by last_active DESC, with optional channel_type filter.

        Returns:
            {
                "sessions": [{session_id, title, created_at, last_active, msg_count}, ...],
                "total": int,
                "page": int,
                "page_size": int,
                "has_more": bool,
            }
        """
        page = max(1, page)
        with self._lock:
            conn = self._connect()
            try:
                if channel_type:
                    total = conn.execute(
                        "SELECT COUNT(*) FROM sessions WHERE channel_type = ?",
                        (channel_type,),
                    ).fetchone()[0]
                    rows = conn.execute(
                        """
                        SELECT session_id, title, created_at, last_active, msg_count
                        FROM sessions
                        WHERE channel_type = ?
                        ORDER BY last_active DESC
                        LIMIT ? OFFSET ?
                        """,
                        (channel_type, page_size, (page - 1) * page_size),
                    ).fetchall()
                else:
                    total = conn.execute(
                        "SELECT COUNT(*) FROM sessions",
                    ).fetchone()[0]
                    rows = conn.execute(
                        """
                        SELECT session_id, title, created_at, last_active, msg_count
                        FROM sessions
                        ORDER BY last_active DESC
                        LIMIT ? OFFSET ?
                        """,
                        (page_size, (page - 1) * page_size),
                    ).fetchall()
            finally:
                conn.close()

        sessions = [
            {
                "session_id": r[0],
                "title": r[1],
                "created_at": r[2],
                "last_active": r[3],
                "msg_count": r[4],
            }
            for r in rows
        ]
        return {
            "sessions": sessions,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": (page - 1) * page_size + page_size < total,
        }

    def rename_session(self, session_id: str, title: str) -> bool:
        """Update the title of a session. Returns True if the session existed."""
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    cur = conn.execute(
                        "UPDATE sessions SET title = ? WHERE session_id = ?",
                        (title, session_id),
                    )
                    return cur.rowcount > 0
            finally:
                conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Return basic stats keyed by channel_type, for monitoring."""
        with self._lock:
            conn = self._connect()
            try:
                total_sessions = conn.execute(
                    "SELECT COUNT(*) FROM sessions"
                ).fetchone()[0]
                total_messages = conn.execute(
                    "SELECT COUNT(*) FROM messages"
                ).fetchone()[0]
                by_channel = conn.execute(
                    """
                    SELECT channel_type, COUNT(*) as cnt
                    FROM sessions
                    GROUP BY channel_type
                    ORDER BY cnt DESC
                    """
                ).fetchall()
                return {
                    "total_sessions": total_sessions,
                    "total_messages": total_messages,
                    "by_channel": {row[0] or "unknown": row[1] for row in by_channel},
                }
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(_DDL)
            conn.commit()
            self._migrate(conn)
        finally:
            conn.close()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Apply incremental schema migrations on existing databases."""
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "channel_type" not in cols:
            try:
                conn.execute(_MIGRATION_ADD_CHANNEL_TYPE)
                conn.commit()
                logger.info("[ConversationStore] Migrated: added channel_type column")
            except Exception as e:
                logger.warning(f"[ConversationStore] Migration failed: {e}")
        if "title" not in cols:
            try:
                conn.execute(_MIGRATION_ADD_TITLE)
                conn.commit()
                logger.info("[ConversationStore] Migrated: added title column")
            except Exception as e:
                logger.warning(f"[ConversationStore] Migration (title) failed: {e}")
        if "context_start_seq" not in cols:
            try:
                conn.execute(_MIGRATION_ADD_CONTEXT_START_SEQ)
                conn.commit()
                logger.info("[ConversationStore] Migrated: added context_start_seq column")
            except Exception as e:
                logger.warning(f"[ConversationStore] Migration (context_start_seq) failed: {e}")

        msg_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "extras" not in msg_cols:
            try:
                conn.execute(_MIGRATION_ADD_MSG_EXTRAS)
                conn.commit()
                logger.info("[ConversationStore] Migrated: added messages.extras column")
            except Exception as e:
                logger.warning(f"[ConversationStore] Migration (extras) failed: {e}")
        if "thread_id" not in msg_cols:
            try:
                conn.execute(_MIGRATION_ADD_MSG_THREAD_ID)
                conn.commit()
                logger.info("[ConversationStore] Migrated: added messages.thread_id column")
            except Exception as e:
                logger.warning(f"[ConversationStore] Migration (thread_id) failed: {e}")
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session_thread "
                "ON messages (session_id, thread_id, seq)"
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"[ConversationStore] thread index migration failed: {e}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_store_instance: Optional[ConversationStore] = None
_store_lock = threading.Lock()


def get_conversation_store() -> ConversationStore:
    """
    Return the process-wide ConversationStore singleton.

    Reuses the long-term memory database so the project stays with a single
    SQLite file: ~/lightagent/memory/long-term/index.db
    The conversation tables (sessions / messages) are separate from the
    memory tables (memory_chunks / file_metadata) — no conflicts.
    """
    global _store_instance
    if _store_instance is not None:
        return _store_instance

    with _store_lock:
        if _store_instance is not None:
            return _store_instance

        try:
            from agent.memory.config import get_default_memory_config
            db_path = get_default_memory_config().get_db_path()
        except Exception:
            from common.utils import expand_path
            db_path = Path(expand_path("~/lightagent")) / "memory" / "long-term" / "index.db"

        _store_instance = ConversationStore(db_path)
        logger.debug(f"[ConversationStore] Using shared DB at: {db_path}")
        return _store_instance

