"""Runtime emotion model for WeChat group behavior."""

from __future__ import annotations

import copy
import datetime as dt
import re
import time
from typing import Dict, Optional

from channel.wechat_group.wechat_group_emotion_store import WechatGroupEmotionStore
from config import conf


class WechatGroupEmotionService:
    def __init__(self, store: Optional[WechatGroupEmotionStore] = None):
        self.store = store or WechatGroupEmotionStore()

    def get_state(self, room_id: str, now=None) -> Dict:
        now_ts = _coerce_timestamp(now)
        row = self.store.get_state(room_id)
        if not row:
            return self.store.upsert_state(
                room_id=room_id,
                valence=self._default_valence(),
                energy=self._default_energy(),
                sociability=self._default_sociability(),
                last_decay_at=now_ts,
                last_reply_at=0,
                reply_count_1h=0,
                updated_at=now_ts,
            )
        return self._apply_decay(dict(row), now_ts)

    def observe_message(self, room_id: str, text: str, is_at: bool = False, now=None) -> Dict:
        now_ts = _coerce_timestamp(now)
        state = self.get_state(room_id, now=now_ts)
        raw_text = str(text or "")
        normalized = re.sub(r"\s+", "", raw_text)
        if is_at or "?" in raw_text or "？" in raw_text:
            state["sociability"] = _clamp(state["sociability"] + 0.12, 0.0, 1.0)
            state["energy"] = _clamp(state["energy"] + 0.04, 0.0, 1.0)
            state["valence"] = _clamp(state["valence"] + 0.02, -1.0, 1.0)
        if len(normalized) <= 2:
            state["sociability"] = _clamp(state["sociability"] - 0.08, 0.0, 1.0)
            state["valence"] = _clamp(state["valence"] - 0.03, -1.0, 1.0)
        state["last_decay_at"] = now_ts
        state["updated_at"] = now_ts
        return self._save(state)

    def mark_replied(self, room_id: str, now=None) -> Dict:
        now_ts = _coerce_timestamp(now)
        state = self.get_state(room_id, now=now_ts)
        last_reply_at = int(state.get("last_reply_at") or 0)
        recent_count = int(state.get("reply_count_1h") or 0)
        if last_reply_at and now_ts - last_reply_at >= 3600:
            recent_count = 0
        recent_count += 1
        state["last_reply_at"] = now_ts
        state["reply_count_1h"] = recent_count
        state["energy"] = _clamp(state["energy"] - min(0.08 + recent_count * 0.01, 0.2), 0.0, 1.0)
        state["updated_at"] = now_ts
        state["last_decay_at"] = now_ts
        return self._save(state)

    def reset_state(self, room_id: str, now=None) -> Dict:
        now_ts = _coerce_timestamp(now)
        return self.store.upsert_state(
            room_id=str(room_id or "").strip(),
            valence=self._default_valence(),
            energy=self._default_energy(),
            sociability=self._default_sociability(),
            last_decay_at=now_ts,
            last_reply_at=0,
            reply_count_1h=0,
            updated_at=now_ts,
        )

    def adjust_free_reply_decision(self, decision: Dict, room_id: str, now=None) -> Dict:
        adjusted = copy.deepcopy(decision or {})
        now_ts = _coerce_timestamp(now or adjusted.get("timestamp"))
        state = self.get_state(room_id, now=now_ts)
        suppressions = adjusted.setdefault("suppressions", [])
        threshold = int(adjusted.get("threshold", 0) or 0)
        if state["sociability"] < 0.2 and "emotion_low_sociability" not in suppressions:
            suppressions.append("emotion_low_sociability")
        if state["energy"] < 0.15 and "emotion_low_energy" not in suppressions:
            suppressions.append("emotion_low_energy")
        if self._is_time_rule_blocked(now_ts) and "time_rule_blocked" not in suppressions:
            suppressions.append("time_rule_blocked")
        if state["valence"] < -0.4:
            threshold += 5
        adjusted["threshold"] = threshold
        if int(adjusted.get("score", 0) or 0) < threshold and "below_threshold" not in suppressions:
            suppressions.append("below_threshold")
        adjusted["triggered"] = not suppressions
        adjusted["emotion"] = {
            "valence": state["valence"],
            "energy": state["energy"],
            "sociability": state["sociability"],
            "interpreted_state": self.interpret_state(state),
        }
        return adjusted

    def build_prompt_block(self, room_id: str, now=None) -> str:
        state = self.get_state(room_id, now=now)
        return (
            "<wechat-group-emotion>\n"
            "valence: {valence}\n"
            "energy: {energy}\n"
            "sociability: {sociability}\n"
            "interpreted_state: {interpreted_state}\n"
            "</wechat-group-emotion>"
        ).format(
            valence=round(float(state["valence"]), 3),
            energy=round(float(state["energy"]), 3),
            sociability=round(float(state["sociability"]), 3),
            interpreted_state=self.interpret_state(state),
        )

    @staticmethod
    def interpret_state(state: Dict) -> str:
        energy = float(state.get("energy", 0))
        sociability = float(state.get("sociability", 0))
        valence = float(state.get("valence", 0))
        if sociability < 0.2 or energy < 0.15:
            return "withdrawn"
        if energy > 0.7 and sociability > 0.7:
            return "engaged"
        if valence < -0.3:
            return "guarded"
        return "steady"

    def _apply_decay(self, state: Dict, now_ts: int) -> Dict:
        last_decay_at = int(state.get("last_decay_at") or 0)
        if last_decay_at <= 0:
            state["last_decay_at"] = now_ts
            return state
        decay_seconds = max(int(conf().get("wechat_group_emotion_decay_minutes", 10) or 10), 1) * 60
        elapsed = max(now_ts - last_decay_at, 0)
        if elapsed < decay_seconds:
            return state
        factor = min(elapsed / float(decay_seconds), 3.0)
        state["valence"] = _approach(state["valence"], self._default_valence(), 0.08 * factor)
        state["energy"] = _approach(state["energy"], self._default_energy(), 0.1 * factor)
        state["sociability"] = _approach(state["sociability"], self._default_sociability(), 0.1 * factor)
        if int(state.get("last_reply_at") or 0) and now_ts - int(state.get("last_reply_at") or 0) >= 3600:
            state["reply_count_1h"] = 0
        state["last_decay_at"] = now_ts
        state["updated_at"] = now_ts
        return self._save(state)

    def _is_time_rule_blocked(self, now_ts: int) -> bool:
        if not conf().get("wechat_group_free_reply_time_rules_enabled", False):
            return False
        rules = conf().get("wechat_group_free_reply_time_rules", []) or []
        if not isinstance(rules, list) or not rules:
            return False
        current = dt.datetime.fromtimestamp(now_ts, dt.timezone.utc)
        weekday = current.strftime("%a").lower()[:3]
        now_minutes = current.hour * 60 + current.minute
        for item in rules:
            if not isinstance(item, dict):
                continue
            days = [str(day or "").strip().lower()[:3] for day in item.get("days") or []]
            if days and weekday not in days:
                continue
            start = _parse_hhmm(str(item.get("start") or "00:00"))
            end = _parse_hhmm(str(item.get("end") or "23:59"))
            if start <= now_minutes <= end:
                return False
        return True

    def _save(self, state: Dict) -> Dict:
        return self.store.upsert_state(
            room_id=str(state.get("room_id") or ""),
            valence=float(state.get("valence", 0)),
            energy=float(state.get("energy", 0)),
            sociability=float(state.get("sociability", 0)),
            last_decay_at=int(state.get("last_decay_at") or 0),
            last_reply_at=int(state.get("last_reply_at") or 0),
            reply_count_1h=int(state.get("reply_count_1h") or 0),
            updated_at=int(state.get("updated_at") or 0),
        )

    @staticmethod
    def _default_valence() -> float:
        return _clamp(float(conf().get("wechat_group_emotion_default_valence", 0) or 0), -1.0, 1.0)

    @staticmethod
    def _default_energy() -> float:
        return _clamp(float(conf().get("wechat_group_emotion_default_energy", 0.5) or 0.5), 0.0, 1.0)

    @staticmethod
    def _default_sociability() -> float:
        return _clamp(float(conf().get("wechat_group_emotion_default_sociability", 0.45) or 0.45), 0.0, 1.0)


def _coerce_timestamp(value=None) -> int:
    try:
        return int(value)
    except Exception:
        return int(time.time())


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def _approach(value: float, target: float, step: float) -> float:
    value = float(value)
    target = float(target)
    if value < target:
        return min(value + step, target)
    if value > target:
        return max(value - step, target)
    return value


def _parse_hhmm(value: str) -> int:
    try:
        hour, minute = value.split(":", 1)
        return max(0, min(int(hour), 23)) * 60 + max(0, min(int(minute), 59))
    except Exception:
        return 0
