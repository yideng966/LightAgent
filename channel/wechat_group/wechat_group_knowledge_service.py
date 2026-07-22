"""Service layer for WeChat group-scoped knowledge."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore


class WechatGroupKnowledgeService:
    def __init__(self, store: Optional[WechatGroupKnowledgeStore] = None):
        self.store = store or WechatGroupKnowledgeStore()

    def list_group_memories(
        self,
        room_id: str,
        query: str = "",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return self.store.list_group_memories(room_id=room_id, query=query, limit=limit)

    def add_group_memory(
        self,
        room_id: str,
        content: str,
        evidence_message_ids: Optional[List[str]] = None,
        evidence_text: str = "",
        source_kind: str = "manual",
    ) -> Dict[str, Any]:
        return self.store.add_group_memory(
            room_id=room_id,
            content=content,
            evidence_message_ids=evidence_message_ids or [],
            evidence_text=evidence_text,
            source_kind=source_kind,
        )

    def disable_group_memory(self, room_id: str, memory_id: str) -> bool:
        return self.store.update_group_memory_status(room_id, memory_id, "inactive")

    def search_group_memories(
        self,
        room_id: str,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        max_limit = min(max(int(limit or 5), 1), 50)
        query_text = _normalize_lookup_text(query)
        rows = self.store.list_group_memories(room_id=room_id, limit=200)
        if query_text:
            matched = [
                row for row in rows
                if query_text in _normalize_lookup_text(row.get("content", ""))
                or query_text in _normalize_lookup_text(row.get("evidence_text", ""))
            ]
            if matched:
                matched.sort(key=lambda item: (-int(item.get("updated_at") or 0), item.get("memory_id") or ""))
                return matched[:max_limit]
        return rows[:max_limit]


def _normalize_lookup_text(value: Any) -> str:
    return "".join(str(value or "").strip().lower().split())
