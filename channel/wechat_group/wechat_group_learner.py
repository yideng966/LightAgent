"""Heuristic learner for room-scoped profiles and group knowledge."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
from channel.wechat_group.wechat_group_transport import project_wechat_message_type


_COMMON_WORD_STOPWORDS = {
    "今天", "晚上", "一下", "继续", "确认", "本群", "统一",
    "amp", "lt", "gt", "quot", "apos", "nbsp",
    "biztype", "size", "msg", "emoji", "xml", "html", "span", "div",
    "src", "href", "http", "https", "www", "com", "md",
    "bizid", "duration", "revokemsg",
}

_COMMON_WORD_ASCII_ALLOWLIST = {
    "ai", "api", "asr", "css", "dns", "gpt", "ios", "ip", "js", "kfc",
    "llm", "nas", "npm", "pt", "qa", "rag", "sql", "ssh", "ssl", "tcl",
    "tts", "tv", "ui", "ux", "vpn", "vps",
    "appletv", "docker", "fastapi", "flask", "linux", "next", "python",
    "react", "sqlite", "vite", "vue", "wechat", "wechaty",
}


class WechatGroupLearner:
    def __init__(
        self,
        archive: WechatGroupArchive,
        profile_service: WechatGroupProfileService,
        knowledge_service: WechatGroupKnowledgeService,
        knowledge_store: Optional[WechatGroupKnowledgeStore] = None,
        config_getter=None,
    ):
        self.archive = archive
        self.profile_service = profile_service
        self.knowledge_service = knowledge_service
        self.knowledge_store = knowledge_store or knowledge_service.store
        self.profile_store = profile_service.store
        self.config_getter = config_getter or (lambda key, default=None: default)

    def run_once(self, room_id: str, mode: str = "all") -> Dict[str, Any]:
        room_text = str(room_id or "").strip()
        mode_text = str(mode or "all").strip().lower()
        if not room_text:
            raise ValueError("stable_room_id is required")
        if mode_text not in {"all", "profile", "memory"}:
            raise ValueError("mode must be all, profile, or memory")

        profile_result = self._run_profile_pipeline(room_text) if mode_text in {"all", "profile"} else {}
        memory_result = self._run_memory_pipeline(room_text, mode_text) if mode_text in {"all", "memory"} else {}
        return {
            "status": "success",
            "run_id": memory_result.get("run_id") or profile_result.get("run_id") or "",
            "profile_run_id": profile_result.get("run_id") or "",
            "memory_run_id": memory_result.get("run_id") or "",
            "batch_message_count": max(
                int(profile_result.get("batch_message_count") or 0),
                int(memory_result.get("batch_message_count") or 0),
            ),
            "profile_batch_message_count": int(profile_result.get("batch_message_count") or 0),
            "memory_batch_message_count": int(memory_result.get("batch_message_count") or 0),
            "profile_update_count": int(profile_result.get("profile_update_count") or 0),
            "group_memory_upsert_count": int(memory_result.get("group_memory_upsert_count") or 0),
            "profiles": profile_result.get("profiles") or [],
            "group_memories": memory_result.get("group_memories") or [],
        }

    def _run_profile_pipeline(self, room_id: str) -> Dict[str, Any]:
        state = self.profile_store.get_learning_state(room_id, pipeline="heuristic")
        if int(state.get("updated_at") or 0) == 0:
            baseline = self.archive.get_max_row_id(room_id)
            state = self.profile_store.update_learning_state(
                room_id,
                pipeline="heuristic",
                last_archive_row_id=baseline,
                latest_observed_row_id=baseline,
            )
        batch_limit = int(self._cfg("wechat_group_learning_batch_message_limit", 200) or 200)
        batch_start_row_id = int(state.get("last_archive_row_id") or 0)
        run_id = self.profile_store.create_run(
            room_id,
            trigger_source="manual",
            batch_start_row_id=batch_start_row_id,
            pipeline="heuristic",
        )
        self.profile_store.update_learning_state(
            room_id,
            pipeline="heuristic",
            running=True,
        )
        try:
            messages = self.archive.get_messages_after_row_id(room_id, batch_start_row_id, limit=batch_limit)
            profiles = []
            if messages:
                profiles = _merge_profile_results(
                    self._learn_profiles(room_id, messages),
                    self._learn_mentioned_aliases(room_id, messages),
                )
            batch_end_row_id = int(messages[-1].get("id") or batch_start_row_id) if messages else batch_start_row_id
            self.profile_store.finish_run(
                run_id,
                status="success",
                batch_end_row_id=batch_end_row_id,
                batch_message_count=len(messages),
                analyzed_member_count=len({_profile_subject_id(item) for item in messages if _profile_subject_id(item)}),
                profile_update_count=len(profiles),
            )
            self.profile_store.update_learning_state(
                room_id,
                pipeline="heuristic",
                last_archive_row_id=batch_end_row_id,
                latest_observed_row_id=batch_end_row_id,
                last_success_at=int(time.time()),
                running=False,
                last_failed_reason="",
            )
            return {
                "run_id": run_id,
                "batch_message_count": len(messages),
                "profile_update_count": len(profiles),
                "profiles": profiles,
            }
        except Exception as exc:
            self.profile_store.finish_run(
                run_id,
                status="failed",
                batch_end_row_id=batch_start_row_id,
                failed_reason=str(exc),
            )
            self.profile_store.update_learning_state(
                room_id,
                pipeline="heuristic",
                running=False,
                last_failed_at=int(time.time()),
                last_failed_reason=str(exc),
            )
            raise

    def _run_memory_pipeline(self, room_id: str, mode: str) -> Dict[str, Any]:
        cursor = self.knowledge_store.get_cursor(room_id)
        batch_limit = int(self._cfg("wechat_group_learning_batch_message_limit", 200) or 200)
        batch_start_row_id = int(cursor.get("last_archive_row_id") or 0)
        run_id = self.knowledge_store.create_learning_run(room_id, mode, batch_start_row_id)
        try:
            messages = self.archive.get_messages_after_row_id(room_id, batch_start_row_id, limit=batch_limit)
            if not messages:
                self.knowledge_store.finish_learning_run(
                    run_id=run_id,
                    status="success",
                    batch_end_row_id=batch_start_row_id,
                    batch_message_count=0,
                    profile_update_count=0,
                    group_memory_upsert_count=0,
                )
                return {
                    "status": "success",
                    "run_id": run_id,
                    "batch_message_count": 0,
                    "group_memory_upsert_count": 0,
                    "group_memories": [],
                }

            group_memories = self._learn_group_memories(room_id, messages)
            batch_end_row_id = int(messages[-1].get("id") or batch_start_row_id)
            self.knowledge_store.update_cursor(room_id, batch_end_row_id)
            self.knowledge_store.finish_learning_run(
                run_id=run_id,
                status="success",
                batch_end_row_id=batch_end_row_id,
                batch_message_count=len(messages),
                profile_update_count=0,
                group_memory_upsert_count=len(group_memories),
            )
            return {
                "status": "success",
                "run_id": run_id,
                "batch_message_count": len(messages),
                "group_memory_upsert_count": len(group_memories),
                "group_memories": group_memories,
            }
        except Exception as exc:
            self.knowledge_store.finish_learning_run(
                run_id=run_id,
                status="failed",
                batch_end_row_id=batch_start_row_id,
                batch_message_count=0,
                profile_update_count=0,
                group_memory_upsert_count=0,
                failed_reason=str(exc),
            )
            raise

    def _learn_profiles(self, room_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in messages:
            sender_id = _profile_subject_id(item)
            if not sender_id or not _is_learnable_text_message(item):
                continue
            grouped[sender_id].append(item)

        min_messages = max(int(self._cfg("wechat_group_learning_profile_min_messages", 6) or 6), 1)
        sample_limit = max(int(self._cfg("wechat_group_learning_profile_sample_limit", 30) or 30), 1)
        results = []
        for sender_id, rows in grouped.items():
            if len(rows) < min_messages:
                continue
            sample_rows = rows[:sample_limit]
            nickname = _pick_sender_nickname(sender_id, sample_rows)
            text_blob = " ".join(str(row.get("text") or "") for row in sample_rows)
            common_words = _top_terms(text_blob, limit=3)
            interests = _infer_interests(text_blob)
            speak_style = _infer_speak_style(sample_rows)
            profile = self.profile_service.merge_learned_profile(
                sender_id=sender_id,
                primary_nickname=nickname,
                aliases=[nickname] if nickname and nickname != sender_id else [],
                speak_style=speak_style,
                interests=interests,
                common_words=common_words,
                msg_delta=len(sample_rows),
                activity_delta=len(sample_rows),
                intimacy_delta=1 if any((row.get("is_at") or 0) for row in sample_rows) else 0,
                room_id=room_id,
                room_name=str(sample_rows[-1].get("room_name") or ""),
                last_seen_at=int(sample_rows[-1].get("created_at") or 0),
            )
            if profile:
                results.append(profile)
        return results

    def _learn_mentioned_aliases(self, room_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        collected: Dict[str, Dict[str, Any]] = {}
        for item in messages:
            resolved = _resolve_single_mentioned_alias(item)
            if not resolved:
                continue
            target_sender_id, alias = resolved
            bucket = collected.setdefault(target_sender_id, {
                "aliases": [],
                "room_name": str(item.get("room_name") or ""),
                "last_seen_at": 0,
            })
            if alias not in bucket["aliases"]:
                bucket["aliases"].append(alias)
            if not bucket["room_name"]:
                bucket["room_name"] = str(item.get("room_name") or "")
            bucket["last_seen_at"] = max(int(bucket["last_seen_at"] or 0), int(item.get("created_at") or 0))

        results = []
        for target_sender_id, payload in collected.items():
            profile = self.profile_service.merge_learned_aliases(
                sender_id=target_sender_id,
                aliases=payload["aliases"],
                room_id=room_id,
                room_name=payload["room_name"],
                last_seen_at=payload["last_seen_at"],
            )
            if profile:
                results.append(profile)
        return results

    def _learn_group_memories(self, room_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        min_messages = max(int(self._cfg("wechat_group_learning_group_memory_min_messages", 20) or 20), 1)
        keyword_rows = [
            item for item in messages
            if _is_learnable_text_message(item)
            and _looks_like_group_memory(str(item.get("text") or ""))
        ]
        if len(keyword_rows) < min_messages:
            return []

        memory_text = _merge_memory_texts([str(item.get("text") or "") for item in keyword_rows])
        existing = self.knowledge_service.search_group_memories(room_id, memory_text, limit=5)
        if any(_normalize_text(item.get("content", "")) == _normalize_text(memory_text) for item in existing):
            return []

        memory = self.knowledge_service.add_group_memory(
            room_id=room_id,
            content=memory_text,
            evidence_message_ids=[str(item.get("message_id") or "") for item in keyword_rows if item.get("message_id")],
            evidence_text=" | ".join(str(item.get("text") or "") for item in keyword_rows[:3]),
            source_kind="learning",
        )
        return [memory]

    def _cfg(self, key: str, default=None):
        return self.config_getter(key, default)


def _infer_speak_style(rows: List[Dict[str, Any]]) -> str:
    texts = [str(row.get("text") or "").strip() for row in rows if str(row.get("text") or "").strip()]
    if not texts:
        return ""
    avg_len = sum(len(text) for text in texts) / len(texts)
    if any(token in "".join(texts) for token in ("1.", "2.", "首先", "其次", "清单")):
        return "更爱列清单"
    if avg_len <= 15:
        return "短句，偏直接"
    return "表达完整，偏说明式"


def _infer_interests(text: str) -> List[str]:
    mapping = {
        "前端": ["前端", "react", "ui", "样式"],
        "发布": ["发布", "发版", "版本"],
        "测试": ["测试", "回归", "qa"],
        "架构": ["架构", "重构"],
    }
    lowered = text.lower()
    result = []
    for label, keywords in mapping.items():
        if any(keyword in lowered for keyword in keywords):
            result.append(label)
    return result


def _top_terms(text: str, limit: int = 3) -> List[str]:
    tokens = re.findall(r"[A-Za-z]{2,}|[\u4e00-\u9fff]{2,}", text or "")
    counts: Dict[str, int] = {}
    for token in tokens:
        normalized = _normalize_common_word_token(token)
        if not normalized:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ordered[:limit]]


def _normalize_common_word_token(token: str) -> str:
    text = str(token or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in _COMMON_WORD_STOPWORDS:
        return ""
    if re.fullmatch(r"[\u4e00-\u9fff]{2,}", text):
        return text
    if not re.fullmatch(r"[a-z0-9]+", lowered):
        return ""
    if re.fullmatch(r"[0-9]+", lowered):
        return ""
    if re.fullmatch(r"[0-9a-f]{2,}", lowered) and lowered not in _COMMON_WORD_ASCII_ALLOWLIST:
        return ""
    if len(lowered) <= 3 and lowered not in _COMMON_WORD_ASCII_ALLOWLIST:
        return ""
    return lowered


def _looks_like_group_memory(text: str) -> bool:
    lowered = _normalize_text(text)
    return any(keyword in lowered for keyword in ("发版", "发布", "固定", "统一", "规则", "约定"))


def _merge_memory_texts(texts: List[str]) -> str:
    if not texts:
        return ""
    normalized = [_normalize_text(text) for text in texts if _normalize_text(text)]
    if not normalized:
        return ""
    first = normalized[0]
    for candidate in normalized[1:]:
        if candidate == first:
            continue
        if first in candidate:
            first = candidate
        elif candidate in first:
            continue
        else:
            return texts[-1].strip()
    return texts[-1].strip()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+|[，。,.!！?？:：]", "", text or "").lower()


def _merge_profile_results(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for group in groups:
        for profile in group or []:
            sender_id = str((profile or {}).get("sender_id") or "").strip()
            if sender_id:
                merged[sender_id] = profile
    return list(merged.values())


def _profile_subject_id(row: Dict[str, Any]) -> str:
    return str(row.get("stable_member_id") or row.get("sender_id") or "").strip()


def _resolve_single_mentioned_alias(row: Dict[str, Any]) -> Optional[tuple[str, str]]:
    if not _is_learnable_text_message(row):
        return None
    sender_id = str(row.get("sender_id") or "").strip()
    text = str(row.get("text") or "")
    if not sender_id or not text.strip():
        return None
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    mention_ids = [
        str(item or "").strip()
        for item in (metadata.get("at_list") or row.get("at_list") or [])
        if str(item or "").strip()
    ]
    self_id = str(metadata.get("self_id") or "").strip()
    target_ids = []
    for mentioned_id in mention_ids:
        if mentioned_id == sender_id:
            continue
        if self_id and mentioned_id == self_id:
            continue
        if mentioned_id not in target_ids:
            target_ids.append(mentioned_id)
    if len(target_ids) != 1:
        return None

    bot_name = _normalize_name_lookup(metadata.get("self_display_name"))
    mention_names = []
    for item in _extract_explicit_mention_names(text):
        alias = _normalize_mention_alias(item)
        if not alias:
            continue
        if bot_name and _normalize_name_lookup(alias) == bot_name:
            continue
        if alias not in mention_names:
            mention_names.append(alias)
    if len(mention_names) != 1:
        return None
    return target_ids[0], mention_names[0]


def _is_learnable_text_message(row: Dict[str, Any]) -> bool:
    return project_wechat_message_type(
        row.get("message_type") or "text",
        row.get("text"),
    ) == "text"


def _extract_explicit_mention_names(text: str) -> List[str]:
    pattern = r"[@＠]([^\s\u2005\u2006\u2007\u2008\u2009\u200a,，。:：;；!?！？]{1,40})"
    return [match.group(1) for match in re.finditer(pattern, text or "")]


def _normalize_mention_alias(value: Any) -> str:
    text = str(value or "").replace("\u2005", " ").replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text).strip(" ,，。:：;；!?！？")
    text = text.lstrip("@＠").strip()
    if not text or _looks_like_raw_sender_name(text):
        return ""
    if len(text) == 1 and not re.search(r"[A-Za-z0-9]", text):
        return ""
    return text[:40]


def _normalize_name_lookup(value: Any) -> str:
    return "".join(str(value or "").replace("\u2005", " ").strip().lower().split())


def _pick_sender_nickname(sender_id: str, rows: List[Dict[str, Any]]) -> str:
    for row in reversed(rows or []):
        nickname = str(row.get("sender_nickname") or "").strip()
        if nickname and not _looks_like_raw_sender_name(nickname, sender_id):
            return nickname
    return str(sender_id or "").strip()


def _looks_like_raw_sender_name(value: Any, sender_id: str = "") -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = text.lstrip("@")
    sender_text = str(sender_id or "").strip()
    sender_normalized = sender_text.lstrip("@")
    if sender_text and text == sender_text:
        return True
    if sender_normalized and normalized == sender_normalized:
        return True
    if normalized.startswith("wxid_"):
        return True
    if text.startswith("@") and re.fullmatch(r"[0-9A-Za-z_-]{12,}", normalized):
        return True
    return False
