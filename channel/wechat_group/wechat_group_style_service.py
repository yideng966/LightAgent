"""Runtime helpers for WeChat group style cards."""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional

from channel.wechat_group.wechat_group_style_store import WechatGroupStyleStore
from channel.wechat_group.wechat_group_transport import (
    is_wechat_transport_xml,
    project_wechat_message_type,
)
from config import conf


class WechatGroupStyleService:
    def __init__(self, store: Optional[WechatGroupStyleStore] = None):
        self.store = store or WechatGroupStyleStore()

    def list_candidates(self, room_id: str, limit: int = 20) -> List[Dict]:
        return self.store.list_styles(room_id, status="candidate", limit=limit)

    def list_active_styles(self, room_id: str, limit: Optional[int] = None) -> List[Dict]:
        if limit is None:
            limit = int(conf().get("wechat_group_style_context_limit", 3) or 3)
        return self.store.list_styles(room_id, status="active", limit=limit)

    def review_style(self, room_id: str, style_id: str, action: str = "approve") -> Dict:
        action_text = str(action or "approve").strip().lower()
        status = {
            "approve": "active",
            "reject": "rejected",
            "disable": "disabled",
        }.get(action_text, "active")
        return self.store.update_status(room_id, style_id, status=status)

    def build_prompt_block_from_archive(self, archive, room_id: str, now=None) -> str:
        if conf().get("wechat_group_style_learning_enabled", True):
            self.refresh_candidates_from_archive(archive, room_id, now=now)
        return self.build_prompt_block(room_id)

    def refresh_candidates_from_archive(self, archive, room_id: str, now=None) -> List[Dict]:
        messages = archive.get_recent_messages(
            room_id,
            limit=int(conf().get("wechat_group_style_learning_batch_limit", 100) or 100),
            minutes=max(int(conf().get("wechat_group_recent_context_minutes", 60) or 60), 60),
            now=now,
        )
        texts = [
            str(item.get("text") or "").strip()
            for item in messages
            if project_wechat_message_type(item.get("message_type") or "text", item.get("text")) == "text"
            and str(item.get("text") or "").strip()
        ]
        evidence = [text for text in texts if len(_normalize_text(text)) >= 4]
        min_evidence = max(int(conf().get("wechat_group_style_candidate_min_evidence", 2) or 2), 1)
        if len(evidence) < min_evidence:
            return []
        intent = _infer_intent(evidence)
        tone = _infer_tone(evidence)
        trigger_rule = _build_trigger_rule(intent)
        avoid_rule = _build_avoid_rule(tone)
        example = _pick_example(evidence)
        status = "active" if conf().get("wechat_group_style_auto_apply_enabled", False) else "candidate"
        style_id = hashlib.sha1(
            "|".join([str(room_id or ""), intent, tone, trigger_rule, avoid_rule]).encode("utf-8")
        ).hexdigest()[:24]
        card = self.store.upsert_style_card(
            room_id=room_id,
            style_id=style_id,
            intent=intent,
            tone=tone,
            trigger_rule=trigger_rule,
            avoid_rule=avoid_rule,
            example=example,
            evidence_count=len(evidence),
            status=status,
        )
        return [card]

    def build_prompt_block(self, room_id: str, limit: Optional[int] = None) -> str:
        cards = self.list_active_styles(room_id, limit=limit)
        if not cards:
            return ""
        sections = []
        for card in cards:
            lines = ["[style_card]"]
            if card.get("intent"):
                lines.append(f"intent: {card['intent']}")
            if card.get("tone"):
                lines.append(f"tone: {card['tone']}")
            if card.get("trigger_rule"):
                lines.append(f"trigger_rule: {card['trigger_rule']}")
            if card.get("avoid_rule"):
                lines.append(f"avoid_rule: {card['avoid_rule']}")
            example = str(card.get("example") or "").strip()
            if example and not is_wechat_transport_xml(example):
                lines.append(f"example: {example}")
            sections.append("\n".join(lines))
        return "<wechat-group-style>\n{}\n</wechat-group-style>".format("\n\n".join(sections))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


def _infer_intent(texts: List[str]) -> str:
    blob = " ".join(texts)
    if any(token in blob for token in ("发版", "安排", "同步", "确认", "结论")):
        return "coordination"
    if any(token in blob for token in ("收到", "好的", "明白", "ok", "OK")):
        return "ack"
    if "?" in blob or "？" in blob:
        return "question"
    return "general"


def _infer_tone(texts: List[str]) -> str:
    blob = " ".join(texts)
    avg_len = sum(len(text) for text in texts) / max(len(texts), 1)
    if any(token in blob for token in ("结论", "先", "直接", "别")) or avg_len <= 18:
        return "direct"
    if any(token in blob for token in ("哈哈", "笑死", "doge")):
        return "playful"
    return "steady"


def _build_trigger_rule(intent: str) -> str:
    if intent == "coordination":
        return "适合讨论排期、执行动作和同步结论时"
    if intent == "ack":
        return "适合快速接收、确认或补一句推进时"
    if intent == "question":
        return "适合接住群内追问并快速补充信息时"
    return "适合群内普通交流但需要保持当前群味道时"


def _build_avoid_rule(tone: str) -> str:
    if tone == "direct":
        return "避免长篇铺垫、避免照抄群友原话"
    if tone == "playful":
        return "避免过度玩梗或在严肃讨论里突然失控"
    return "避免口气过重、避免无信息量复述"


def _pick_example(texts: List[str]) -> str:
    for text in reversed(texts):
        if any(token in text for token in ("结论", "先", "收到", "安排", "同步")):
            return text[:120]
    return texts[-1][:120]
