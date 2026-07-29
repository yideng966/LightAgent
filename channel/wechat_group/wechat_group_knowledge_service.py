"""Service layer for WeChat group permanent memory (legacy module name)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore


class WechatGroupKnowledgeService:
    def __init__(
        self,
        store: Optional[WechatGroupKnowledgeStore] = None,
        archive: Optional[WechatGroupArchive] = None,
    ):
        self.store = store or WechatGroupKnowledgeStore()
        self.archive = archive

    def list_group_memories(
        self,
        room_id: str,
        query: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return self.store.list_group_memories(
            room_id=room_id,
            query=query,
            limit=limit,
            offset=offset,
        )

    def count_group_memories(self, room_id: str, query: str = "") -> int:
        return self.store.count_group_memories(room_id=room_id, query=query)

    def add_group_memory(
        self,
        room_id: str,
        content: str,
        evidence_message_ids: Optional[List[str]] = None,
        evidence_text: str = "",
        source_kind: str = "manual",
        source_run_id: str = "",
        confidence: float = 0.0,
    ) -> Dict[str, Any]:
        evidence_ids = [
            str(value or "").strip()
            for value in (evidence_message_ids or [])
            if str(value or "").strip()
        ]
        if evidence_ids:
            archive = self.archive or WechatGroupArchive()
            if any(archive.get_message_by_id(room_id, message_id) is None for message_id in evidence_ids):
                raise ValueError("evidence_message_ids must belong to the current group")
        return self.store.add_group_memory(
            room_id=room_id,
            content=content,
            evidence_message_ids=evidence_ids,
            evidence_text=evidence_text,
            source_kind=source_kind,
            source_run_id=source_run_id,
            confidence=confidence,
        )

    def apply_dream_memories(
        self,
        room_id: str,
        operations: List[Dict[str, Any]],
        run_id: str,
        auto_apply_threshold: float,
    ) -> Dict[str, Any]:
        room_text = str(room_id or "").strip()
        if not room_text:
            raise ValueError("room_id is required")
        existing = self.store.list_group_memories(room_text, limit=200, status="active")
        by_id = {str(item.get("memory_id") or ""): item for item in existing}
        normalized = {
            _normalize_memory_content(item.get("content")): str(item.get("memory_id") or "")
            for item in existing
            if _normalize_memory_content(item.get("content"))
        }
        written = []
        skipped_count = 0
        threshold = min(max(float(auto_apply_threshold or 0.0), 0.0), 1.0)
        for operation in operations or []:
            action = str(operation.get("action") or "").strip().lower()
            content = str(operation.get("content") or "").strip()
            confidence = float(operation.get("confidence") or 0.0)
            target_memory_id = str(operation.get("target_memory_id") or "").strip()
            if confidence < threshold:
                skipped_count += 1
                continue
            normalized_content = _normalize_memory_content(content)
            duplicate_id = normalized.get(normalized_content, "")
            if action == "add":
                if duplicate_id:
                    skipped_count += 1
                    continue
                memory = self.store.add_group_memory(
                    room_id=room_text,
                    content=content,
                    source_kind="deep_dream",
                    source_run_id=run_id,
                    confidence=confidence,
                    evidence_message_ids=operation.get("evidence_message_ids") or [],
                    evidence_text=str(operation.get("evidence_text") or ""),
                )
            elif action == "update":
                if target_memory_id not in by_id:
                    raise ValueError("target memory is not active in the current room")
                if duplicate_id and duplicate_id != target_memory_id:
                    skipped_count += 1
                    continue
                current = by_id[target_memory_id]
                memory = self.store.upsert_group_memory(
                    room_id=room_text,
                    memory_id=target_memory_id,
                    content=content,
                    source_kind="deep_dream",
                    source_run_id=run_id,
                    confidence=confidence,
                    evidence_message_ids=operation.get("evidence_message_ids") or [],
                    evidence_text=str(operation.get("evidence_text") or ""),
                    created_at=int(current.get("created_at") or 0),
                )
            else:
                raise ValueError("unsupported dream memory action")
            written.append(memory)
            normalized[normalized_content] = str(memory.get("memory_id") or target_memory_id)
        return {"memories": written, "written_count": len(written), "skipped_count": skipped_count}

    def disable_group_memory(self, room_id: str, memory_id: str) -> bool:
        return self.store.update_group_memory_status(room_id, memory_id, "inactive")

    def search_group_knowledge(
        self,
        room_id: str,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """兼容旧调用方；新调用统一使用 search_group_memories。"""
        return self.search_group_memories(room_id=room_id, query=query, limit=limit)

    def search_group_memories(
        self,
        room_id: str,
        query: str,
        limit: int = 5,
        min_score: float = 0.2,
    ) -> List[Dict[str, Any]]:
        max_limit = min(max(int(limit or 5), 1), 1000)
        threshold = min(max(float(min_score or 0.0), 0.0), 1.0)
        query_text = _normalize_lookup_text(query)
        if not query_text:
            return []
        rows = self.store.list_group_memories(room_id=room_id, limit=1000)
        matched = []
        for row in rows:
            score, reason = _score_group_memory(row, query_text)
            if score < threshold:
                continue
            item = dict(row)
            item["score"] = round(score, 4)
            item["match_reason"] = reason
            matched.append(item)
        matched.sort(key=lambda item: (
            -float(item.get("score") or 0.0),
            -int(item.get("updated_at") or 0),
            str(item.get("memory_id") or ""),
        ))
        return matched[:max_limit]

    def list_recent_group_memories(self, room_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.store.list_group_memories(
            room_id=room_id,
            limit=min(max(int(limit or 5), 1), 50),
        )


def _normalize_lookup_text(value: Any) -> str:
    return "".join(str(value or "").strip().lower().split())


def _normalize_memory_content(value: Any) -> str:
    return "".join(
        char for char in str(value or "").strip().lower()
        if not char.isspace() and char not in "，。,.!！?？:：;；"
    )


def _score_group_memory(row: Dict[str, Any], query_text: str) -> tuple[float, str]:
    content = _normalize_lookup_text(row.get("content", ""))
    evidence = _normalize_lookup_text(row.get("evidence_text", ""))
    if query_text in content:
        return 1.0, "content_exact"
    if query_text in evidence:
        return 0.85, "evidence_exact"
    query_parts = _lookup_parts(query_text)
    if not query_parts:
        return 0.0, "no_match"
    content_parts = _lookup_parts(content)
    evidence_parts = _lookup_parts(evidence)
    content_overlap = len(query_parts.intersection(content_parts)) / len(query_parts)
    evidence_overlap = len(query_parts.intersection(evidence_parts)) / len(query_parts)
    score = max(content_overlap * 0.8, evidence_overlap * 0.6)
    if score <= 0:
        return 0.0, "no_match"
    return score, "content_overlap" if content_overlap >= evidence_overlap else "evidence_overlap"


def _lookup_parts(value: str) -> set[str]:
    text = _normalize_lookup_text(value)
    if not text:
        return set()
    if len(text) <= 2:
        return {text}
    return {text[index:index + 2] for index in range(len(text) - 1)}
