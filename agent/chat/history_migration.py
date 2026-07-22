"""
Utilities for importing legacy BaiLongmaPro chat history into LightAgent's
conversation store schema.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Optional

from agent.memory.conversation_store import ConversationStore


@dataclass(frozen=True)
class LegacyConversationRow:
    id: int
    role: str
    from_id: str
    to_id: Optional[str]
    content: str
    channel: str
    timestamp: str
    external_party_id: str = ""


@dataclass(frozen=True)
class MigratedMessage:
    role: str
    content: str
    created_at: int
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MigratedSession:
    session_id: str
    channel_type: str
    title: str
    created_at: int
    last_active: int
    messages: List[MigratedMessage]
    source_channel: str
    source_party: str


@dataclass(frozen=True)
class MigrationPlan:
    sessions: List[MigratedSession]
    source_row_count: int
    message_count: int


@dataclass(frozen=True)
class MigrationResult:
    imported_sessions: int
    imported_messages: int
    source_row_count: int
    backup_path: Optional[str]
    dry_run: bool
    session_ids: List[str]


def load_legacy_conversations(source_db_path: Path | str) -> List[LegacyConversationRow]:
    db_path = Path(source_db_path)
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, role, from_id, to_id, content, channel, timestamp, external_party_id
            FROM conversations
            ORDER BY timestamp ASC, id ASC
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        LegacyConversationRow(
            id=int(row[0]),
            role=str(row[1] or ""),
            from_id=str(row[2] or ""),
            to_id=row[3],
            content=str(row[4] or ""),
            channel=str(row[5] or ""),
            timestamp=str(row[6] or ""),
            external_party_id=str(row[7] or ""),
        )
        for row in rows
    ]


def build_migration_plan(
    rows: Iterable[LegacyConversationRow],
    *,
    session_namespace: str = "blmp",
) -> MigrationPlan:
    grouped: dict[tuple[str, str], list[LegacyConversationRow]] = {}
    row_list = list(rows)
    for row in row_list:
        source_party = _resolve_source_party(row)
        source_channel = _normalize_source_channel(row.channel, source_party)
        grouped.setdefault((source_channel, source_party), []).append(row)

    sessions: List[MigratedSession] = []
    message_count = 0
    for (source_channel, source_party), group_rows in grouped.items():
        group_rows.sort(key=lambda item: (_parse_timestamp(item.timestamp), item.id))
        session_id = _build_session_id(source_channel, source_party, session_namespace)
        messages = _build_session_messages(group_rows, source_channel, source_party)
        if not messages:
            continue
        created_at = min(item.created_at for item in messages)
        last_active = max(item.created_at for item in messages)
        title = _build_session_title(source_channel, source_party, messages)
        sessions.append(
            MigratedSession(
                session_id=session_id,
                channel_type="web",
                title=title,
                created_at=created_at,
                last_active=last_active,
                messages=messages,
                source_channel=source_channel,
                source_party=source_party,
            )
        )
        message_count += len(messages)

    sessions.sort(key=lambda item: (item.created_at, item.session_id))
    return MigrationPlan(
        sessions=sessions,
        source_row_count=len(row_list),
        message_count=message_count,
    )


def import_migration_plan(
    plan: MigrationPlan,
    target_db_path: Path | str,
    *,
    create_backup: bool = True,
) -> MigrationResult:
    target_db = Path(target_db_path)
    ConversationStore(target_db)

    backup_path = None
    if create_backup and target_db.exists():
        backup_path = str(create_sqlite_backup(target_db))

    conn = sqlite3.connect(target_db)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        with conn:
            _ensure_sessions_absent(conn, plan.sessions)
            for session in plan.sessions:
                conn.execute(
                    """
                    INSERT INTO sessions
                    (session_id, channel_type, title, context_start_seq, created_at, last_active, msg_count)
                    VALUES (?, ?, ?, 0, ?, ?, ?)
                    """,
                    (
                        session.session_id,
                        session.channel_type,
                        session.title,
                        session.created_at,
                        session.last_active,
                        len(session.messages),
                    ),
                )
                for seq, message in enumerate(session.messages):
                    conn.execute(
                        """
                        INSERT INTO messages
                        (session_id, seq, role, content, created_at, extras)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session.session_id,
                            seq,
                            message.role,
                            json.dumps(
                                [{"type": "text", "text": message.content}],
                                ensure_ascii=False,
                            ),
                            message.created_at,
                            json.dumps(message.extras, ensure_ascii=False)
                            if message.extras else "",
                        ),
                    )
    finally:
        conn.close()

    return MigrationResult(
        imported_sessions=len(plan.sessions),
        imported_messages=plan.message_count,
        source_row_count=plan.source_row_count,
        backup_path=backup_path,
        dry_run=False,
        session_ids=[item.session_id for item in plan.sessions],
    )


def run_legacy_chat_history_migration(
    *,
    source_db_path: Path | str,
    target_db_path: Path | str,
    dry_run: bool = True,
    create_backup: bool = True,
) -> MigrationResult:
    rows = load_legacy_conversations(source_db_path)
    plan = build_migration_plan(rows)
    if dry_run:
        return MigrationResult(
            imported_sessions=len(plan.sessions),
            imported_messages=plan.message_count,
            source_row_count=plan.source_row_count,
            backup_path=None,
            dry_run=True,
            session_ids=[item.session_id for item in plan.sessions],
        )
    return import_migration_plan(plan, target_db_path, create_backup=create_backup)


def create_sqlite_backup(target_db_path: Path | str) -> Path:
    target_db = Path(target_db_path)
    backup_path = target_db.with_name(
        f"{target_db.stem}.migration-backup-{datetime.now().strftime('%Y%m%d%H%M%S')}{target_db.suffix}"
    )
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(target_db)
    try:
        dest = sqlite3.connect(backup_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    return backup_path


def _ensure_sessions_absent(conn: sqlite3.Connection, sessions: Iterable[MigratedSession]) -> None:
    existing = []
    for session in sessions:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session.session_id,),
        ).fetchone()
        if row:
            existing.append(session.session_id)
    if existing:
        raise ValueError("session already exists: {}".format(", ".join(existing)))


def _build_session_messages(
    rows: List[LegacyConversationRow],
    source_channel: str,
    source_party: str,
) -> List[MigratedMessage]:
    messages: List[MigratedMessage] = []
    has_user = any(_map_role(row.role) == "user" for row in rows)
    if not has_user and rows:
        first_ts = _parse_timestamp(rows[0].timestamp)
        messages.append(
            MigratedMessage(
                role="user",
                content=(
                    "[迁移占位] BaiLongmaPro 中该会话只有机器人输出，"
                    "原始库未找到对应用户消息。"
                ),
                created_at=first_ts,
                extras={
                    "migration": {
                        "source_channel": source_channel,
                        "source_party": source_party,
                        "synthetic": True,
                    }
                },
            )
        )
    for row in rows:
        content = (row.content or "").strip()
        if not content:
            continue
        created_at = _parse_timestamp(row.timestamp)
        messages.append(
            MigratedMessage(
                role=_map_role(row.role),
                content=content,
                created_at=created_at,
                extras={
                    "migration": {
                        "legacy_row_id": row.id,
                        "source_channel": source_channel,
                        "source_party": source_party,
                        "legacy_role": row.role,
                        "synthetic": False,
                    }
                },
            )
        )
    return messages


def _build_session_id(source_channel: str, source_party: str, namespace: str) -> str:
    digest = hashlib.sha1(f"{source_channel}|{source_party}".encode("utf-8")).hexdigest()[:12]
    channel_slug = "".join(
        ch.lower() if ch.isalnum() else "_"
        for ch in source_channel
    ).strip("_") or "unknown"
    return f"session_migrated_{namespace}_{channel_slug}_{digest}"


def _build_session_title(
    source_channel: str,
    source_party: str,
    messages: List[MigratedMessage],
) -> str:
    preview = ""
    for message in messages:
        if "迁移占位" in message.content:
            continue
        preview = " ".join(message.content.split())
        if preview:
            break
    if not preview:
        preview = source_party
    preview = preview[:24]
    return f"迁移 {source_channel} | {preview}"


def _resolve_source_party(row: LegacyConversationRow) -> str:
    if row.external_party_id:
        return row.external_party_id
    if row.role == "jarvis" and row.to_id:
        return str(row.to_id)
    if row.role == "user" and row.from_id:
        return row.from_id
    if row.to_id:
        return str(row.to_id)
    return "unknown"


def _normalize_source_channel(channel: str, source_party: str) -> str:
    normalized = (channel or "").strip().upper()
    if normalized:
        return normalized
    if source_party.startswith("wechaty:room:"):
        return "WECHAT"
    return "UNKNOWN"


def _map_role(role: str) -> str:
    if role == "jarvis":
        return "assistant"
    return "user"


def _parse_timestamp(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("legacy timestamp is required")
    normalized = raw.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    return int(dt.timestamp())
