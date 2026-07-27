"""Two-stage LLM Dream service for permanent WeChat group memories."""

from __future__ import annotations

import json
import re
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent.memory.dream_engine import MemoryDreamEngine, MemoryDreamError
from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_memory_material import (
    WechatGroupMemoryMaterialBatch,
    WechatGroupMemoryMaterialBuilder,
    sanitize_group_memory_text,
)


_SUMMARY_SYSTEM_PROMPT = """You distill durable facts and agreements from one WeChat group batch.
Use only the supplied message evidence. Ignore casual chat, greetings, one-off questions,
temporary errors, personality, interests, speaking style, intimacy, identity and permissions.
Return [EMPTY] when nothing has long-term group value. Otherwise return one JSON object:
{"summary":"concise durable group facts","evidence_message_ids":["message-id"]}
Every evidence ID must be copied exactly from the supplied batch. Return JSON only."""

_DREAM_SYSTEM_PROMPT = """You curate permanent memories for one WeChat group.
Merge new durable facts into the supplied active memories without inventing information.
Do not output member profiles, identity, permissions, room IDs, local paths, secrets or
speaker tokens. Automatic curation may add or update, never delete or disable.
Return exactly one JSON object with this schema:
{"memories":[{"action":"add|update","target_memory_token":"M001 or empty for add","content":"durable group fact","confidence":0.0,"evidence_message_ids":["message-id"]}],"dream_summary":"brief audit summary"}
Use only supplied memory tokens and evidence IDs. Return JSON only."""

_FORBIDDEN_OPERATION_FIELDS = {
    "member_token",
    "sender_id",
    "stable_member_id",
    "room_id",
    "stable_room_id",
    "profile",
    "interests",
    "speak_style",
    "intimacy",
}

_GROUP_DREAM_EXECUTION_LOCK = threading.RLock()
_ROOM_DREAM_LOCKS: Dict[str, Any] = {}
_ROOM_DREAM_LOCKS_GUARD = threading.Lock()


class WechatGroupMemoryDreamService:
    def __init__(
        self,
        archive: Optional[WechatGroupArchive] = None,
        knowledge_service: Optional[WechatGroupKnowledgeService] = None,
        dream_engine: Optional[MemoryDreamEngine] = None,
        config_getter: Optional[Callable[[str, Any], Any]] = None,
    ):
        self.archive = archive or WechatGroupArchive()
        self.knowledge_service = knowledge_service or WechatGroupKnowledgeService()
        self.knowledge_store = self.knowledge_service.store
        self.dream_engine = dream_engine or MemoryDreamEngine()
        if config_getter is None:
            from config import conf

            config_getter = lambda key, default=None: conf().get(key, default)
        self.config_getter = config_getter
        self.material_builder = WechatGroupMemoryMaterialBuilder(self.archive)

    def run_once(
        self,
        stable_room_id: str,
        trigger_source: str = "manual",
        force: bool = False,
    ) -> Dict[str, Any]:
        room_id = str(stable_room_id or "").strip()
        if not room_id:
            raise ValueError("stable_room_id is required")
        with _GROUP_DREAM_EXECUTION_LOCK:
            with _get_room_dream_lock(room_id):
                return self._run_once_locked(room_id, trigger_source, force)

    def _run_once_locked(
        self,
        room_id: str,
        trigger_source: str,
        force: bool,
    ) -> Dict[str, Any]:
        cursor = self.knowledge_store.get_cursor(room_id)
        batch_start = int(cursor.get("last_archive_row_id") or 0)
        batch = self.material_builder.build(
            room_id,
            after_row_id=batch_start,
            limit=self._cfg_int("wechat_group_learning_batch_message_limit", 200),
            window_minutes=self._cfg_int("wechat_group_learning_group_memory_window_minutes", 120),
        )
        run_id = self.knowledge_store.create_learning_run(
            room_id,
            "memory",
            batch_start,
            trigger_source=trigger_source,
        )
        min_messages = self._cfg_int("wechat_group_learning_group_memory_min_messages", 20)
        if not batch.messages:
            consumed_filtered_batch = bool(
                batch.scanned_count and batch.batch_end_row_id > batch_start
            )
            if consumed_filtered_batch:
                self.knowledge_store.update_cursor(room_id, batch.batch_end_row_id)
            self._finish_run(
                run_id,
                status="success",
                batch=batch,
                batch_end=batch.batch_end_row_id if consumed_filtered_batch else batch_start,
                summary_status="filtered" if consumed_filtered_batch else "not_run",
                dream_status="skipped" if consumed_filtered_batch else "not_run",
            )
            return self._result(
                status="success",
                run_id=run_id,
                batch=batch,
                summary_status="filtered" if consumed_filtered_batch else "not_run",
                dream_status="skipped" if consumed_filtered_batch else "not_run",
            )

        if len(batch.messages) < min_messages and not force:
            self._finish_run(
                run_id,
                status="skipped",
                batch=batch,
                batch_end=batch_start,
                summary_status="not_run",
                dream_status="not_run",
            )
            return self._result(
                status="skipped",
                run_id=run_id,
                batch=batch,
                summary_status="not_run",
                dream_status="not_run",
            )

        summary_status = "failed"
        dream_status = "not_run"
        try:
            summary, summary_evidence = self._summarize_material(batch)
            if not summary:
                self.knowledge_store.update_cursor(room_id, batch.batch_end_row_id)
                self._finish_run(
                    run_id,
                    status="success",
                    batch=batch,
                    batch_end=batch.batch_end_row_id,
                    summary_status="empty",
                    dream_status="skipped",
                )
                return self._result(
                    status="success",
                    run_id=run_id,
                    batch=batch,
                    summary_status="empty",
                    dream_status="skipped",
                )

            summary_status = "success"
            dream_status = "failed"
            active_memories = self.knowledge_service.list_group_memories(room_id, limit=200)
            memory_tokens = {
                f"M{index:03d}": str(memory.get("memory_id") or "")
                for index, memory in enumerate(active_memories, 1)
            }
            operations, dream_summary = self._distill_memories(
                batch,
                summary=summary,
                summary_evidence=summary_evidence,
                active_memories=active_memories,
                memory_tokens=memory_tokens,
            )
            dream_status = "success"
            applied = self.knowledge_service.apply_dream_memories(
                room_id,
                operations,
                run_id=run_id,
                auto_apply_threshold=self._cfg_float(
                    "wechat_group_learning_auto_apply_threshold",
                    0.9,
                ),
            )
            self.knowledge_store.update_cursor(room_id, batch.batch_end_row_id)
            self._finish_run(
                run_id,
                status="success",
                batch=batch,
                batch_end=batch.batch_end_row_id,
                upsert_count=int(applied.get("written_count") or 0),
                skipped_count=int(applied.get("skipped_count") or 0),
                summary_status="success",
                dream_status="success",
                dream_summary=dream_summary,
            )
            result = self._result(
                status="success",
                run_id=run_id,
                batch=batch,
                summary_status="success",
                dream_status="success",
                memories=applied.get("memories") or [],
                skipped_count=int(applied.get("skipped_count") or 0),
                dream_summary=dream_summary,
            )
            return result
        except Exception as exc:
            status_code = int(getattr(exc, "status_code", 0) or 0)
            transient = bool(getattr(exc, "transient", False))
            self._finish_run(
                run_id,
                status="failed",
                batch=batch,
                batch_end=batch_start,
                summary_status=summary_status,
                dream_status=dream_status,
                failed_reason=_safe_failure_reason(exc),
                llm_status_code=status_code,
            )
            result = self._result(
                status="failed",
                run_id=run_id,
                batch=batch,
                summary_status=summary_status,
                dream_status=dream_status,
            )
            result.update({
                "message": _safe_failure_reason(exc),
                "transient": transient,
                "llm_status_code": status_code,
            })
            return result

    def run_history(self, stable_room_id: str, max_batches: Optional[int] = None) -> Dict[str, Any]:
        room_id = str(stable_room_id or "").strip()
        if not room_id:
            raise ValueError("stable_room_id is required")
        with _GROUP_DREAM_EXECUTION_LOCK:
            with _get_room_dream_lock(room_id):
                return self._run_history_locked(room_id, max_batches)

    def _run_history_locked(self, room_id: str, max_batches: Optional[int]) -> Dict[str, Any]:
        limit = max_batches or self._cfg_int("wechat_group_learning_history_max_batches", 10)
        limit = min(max(int(limit or 1), 1), 100)
        self.knowledge_store.update_cursor(room_id, 0)
        runs = []
        written_count = 0
        skipped_count = 0
        for _ in range(limit):
            before = int(self.knowledge_store.get_cursor(room_id).get("last_archive_row_id") or 0)
            result = self.run_once(room_id, trigger_source="history", force=True)
            runs.append(result)
            written_count += int(result.get("group_memory_upsert_count") or 0)
            skipped_count += int(result.get("skipped_count") or 0)
            after = int(self.knowledge_store.get_cursor(room_id).get("last_archive_row_id") or 0)
            if result.get("status") == "failed" or after <= before or not result.get("batch_message_count"):
                break
        remaining = self.archive.count_text_messages_after_row_id(
            room_id,
            int(self.knowledge_store.get_cursor(room_id).get("last_archive_row_id") or 0),
        )
        last_run = runs[-1] if runs else {}
        status = "failed" if last_run.get("status") == "failed" else "success"
        return {
            "status": status,
            "message": str(last_run.get("message") or ""),
            "transient": bool(last_run.get("transient", False)),
            "llm_status_code": int(last_run.get("llm_status_code") or 0),
            "runs": runs,
            "processed_batches": len(runs),
            "group_memory_upsert_count": written_count,
            "skipped_count": skipped_count,
            "remaining_count": remaining,
        }

    def _summarize_material(
        self,
        batch: WechatGroupMemoryMaterialBatch,
    ) -> Tuple[str, List[str]]:
        raw = self.dream_engine.complete(
            system_prompt=_SUMMARY_SYSTEM_PROMPT,
            user_prompt=json.dumps({"messages": batch.messages}, ensure_ascii=False),
            purpose="wechat_group_memory_daily_summary",
            temperature=0.1,
            max_tokens=800,
        )
        text = str(raw or "").strip()
        if text == "[EMPTY]":
            return "", []
        data = _parse_json_object(text, "group memory summary")
        summary = str(data.get("summary") or "").strip()
        if not summary or summary == "[EMPTY]":
            return "", []
        evidence = _normalize_string_list(data.get("evidence_message_ids"))
        _require_evidence_subset(evidence, batch.evidence_message_ids)
        return summary[:4000], evidence

    def _distill_memories(
        self,
        batch: WechatGroupMemoryMaterialBatch,
        *,
        summary: str,
        summary_evidence: List[str],
        active_memories: List[Dict[str, Any]],
        memory_tokens: Dict[str, str],
    ) -> Tuple[List[Dict[str, Any]], str]:
        token_by_id = {memory_id: token for token, memory_id in memory_tokens.items()}
        prompt_memories = [
            {
                "memory_token": token_by_id.get(str(item.get("memory_id") or ""), ""),
                "content": str(item.get("content") or "")[:1000],
            }
            for item in active_memories
        ]
        raw = self.dream_engine.complete(
            system_prompt=_DREAM_SYSTEM_PROMPT,
            user_prompt=json.dumps({
                "active_memories": prompt_memories,
                "new_summary": summary,
                "summary_evidence_message_ids": summary_evidence,
                "allowed_evidence_message_ids": batch.evidence_message_ids,
            }, ensure_ascii=False),
            purpose="wechat_group_memory_deep_dream",
            temperature=0.2,
            max_tokens=1600,
        )
        data = _parse_json_object(raw, "group memory dream")
        raw_operations = data.get("memories")
        if not isinstance(raw_operations, list):
            raise ValueError("group memory dream memories must be a list")
        if len(raw_operations) > 20:
            raise ValueError("group memory dream returned too many operations")
        evidence_text = {
            item["message_id"]: item["text"]
            for item in batch.messages
        }
        operations = []
        for raw_operation in raw_operations:
            operations.append(_validate_operation(
                raw_operation,
                memory_tokens=memory_tokens,
                allowed_evidence=batch.evidence_message_ids,
                evidence_text=evidence_text,
            ))
        return operations, str(data.get("dream_summary") or "").strip()[:1000]

    def _finish_run(
        self,
        run_id: str,
        *,
        status: str,
        batch: WechatGroupMemoryMaterialBatch,
        batch_end: int,
        upsert_count: int = 0,
        skipped_count: int = 0,
        summary_status: str = "",
        dream_status: str = "",
        dream_summary: str = "",
        failed_reason: str = "",
        llm_status_code: int = 0,
    ) -> None:
        self.knowledge_store.finish_learning_run(
            run_id=run_id,
            status=status,
            batch_end_row_id=batch_end,
            batch_message_count=batch.scanned_count,
            profile_update_count=0,
            group_memory_upsert_count=upsert_count,
            failed_reason=failed_reason,
            summary_status=summary_status,
            dream_status=dream_status,
            skipped_count=skipped_count,
            dream_summary=dream_summary,
            llm_status_code=llm_status_code,
        )

    @staticmethod
    def _result(
        *,
        status: str,
        run_id: str,
        batch: WechatGroupMemoryMaterialBatch,
        summary_status: str,
        dream_status: str,
        memories: Optional[List[Dict[str, Any]]] = None,
        skipped_count: int = 0,
        dream_summary: str = "",
    ) -> Dict[str, Any]:
        written = list(memories or [])
        return {
            "status": status,
            "run_id": run_id,
            "memory_run_id": run_id,
            "batch_message_count": batch.scanned_count,
            "memory_batch_message_count": batch.scanned_count,
            "group_memory_upsert_count": len(written),
            "group_memories": written,
            "skipped_count": int(skipped_count or 0),
            "summary_status": summary_status,
            "dream_status": dream_status,
            "dream_summary": dream_summary,
            "transient": False,
            "llm_status_code": 0,
        }

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            return max(int(self.config_getter(key, default) or default), 1)
        except Exception:
            return default

    def _cfg_float(self, key: str, default: float) -> float:
        try:
            return float(self.config_getter(key, default))
        except Exception:
            return default


def _parse_json_object(value: Any, label: str) -> Dict[str, Any]:
    text = str(value or "").strip()
    try:
        parsed = json.loads(text)
    except Exception as exc:
        raise ValueError(f"{label} response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} response must be a JSON object")
    return parsed


def _get_room_dream_lock(room_id: str):
    room_text = str(room_id or "").strip()
    with _ROOM_DREAM_LOCKS_GUARD:
        lock = _ROOM_DREAM_LOCKS.get(room_text)
        if lock is None:
            lock = threading.RLock()
            _ROOM_DREAM_LOCKS[room_text] = lock
        return lock


def _validate_operation(
    value: Any,
    *,
    memory_tokens: Dict[str, str],
    allowed_evidence: List[str],
    evidence_text: Dict[str, str],
) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("group memory operation must be an object")
    if _FORBIDDEN_OPERATION_FIELDS.intersection(value):
        raise ValueError("group memory operation contains profile or scope fields")
    action = str(value.get("action") or "").strip().lower()
    if action not in {"add", "update"}:
        raise ValueError("group memory action must be add or update")
    token = str(value.get("target_memory_token") or "").strip()
    if action == "update" and token not in memory_tokens:
        raise ValueError("group memory update token is not in the current room")
    if action == "add" and token:
        raise ValueError("group memory add must not target an existing memory")
    content = sanitize_group_memory_text(value.get("content"))
    if len(content) < 4:
        raise ValueError("group memory content is empty or unsafe")
    if re.search(r"(?i)\b(?:speaker_[0-9]+|stable_room_id|sender_id|member_token)\b", content):
        raise ValueError("group memory content exposes opaque identity fields")
    try:
        confidence = float(value.get("confidence"))
    except Exception as exc:
        raise ValueError("group memory confidence is required") from exc
    if confidence < 0 or confidence > 1:
        raise ValueError("group memory confidence must be between 0 and 1")
    evidence = _normalize_string_list(value.get("evidence_message_ids"))
    _require_evidence_subset(evidence, allowed_evidence)
    return {
        "action": action,
        "target_memory_id": memory_tokens.get(token, ""),
        "content": content,
        "confidence": confidence,
        "evidence_message_ids": evidence,
        "evidence_text": " | ".join(evidence_text[item] for item in evidence[:3]),
    }


def _require_evidence_subset(evidence: List[str], allowed: List[str]) -> None:
    if not evidence:
        raise ValueError("group memory evidence is required")
    allowed_set = set(allowed or [])
    if any(item not in allowed_set for item in evidence):
        raise ValueError("group memory evidence is outside the current room batch")


def _normalize_string_list(value: Any) -> List[str]:
    items = value if isinstance(value, list) else []
    result = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _safe_failure_reason(exc: Exception) -> str:
    if isinstance(exc, MemoryDreamError):
        return str(exc)[:500]
    if isinstance(exc, ValueError):
        return str(exc)[:500]
    return f"group memory dream failed: {type(exc).__name__}"
