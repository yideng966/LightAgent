"""LLM-backed extractor for WeChat group member profile candidates."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from channel.wechat_group.wechat_group_transport import project_wechat_message_type


_TRANSIENT_LLM_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class WechatGroupProfileExtractionError(ValueError):
    def __init__(self, message: str, status_code: int = 0, transient: bool = False):
        super().__init__(message)
        self.status_code = int(status_code or 0)
        self.transient = bool(transient)


class WechatGroupProfileLlmExtractor:
    def __init__(self, model: Optional[Any] = None):
        self.model = model

    def extract(
        self,
        room_id: str,
        room_name: str,
        messages: List[Dict[str, Any]],
        existing_profiles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not self.model:
            raise ValueError("model is required for LLM profile extraction")
        prompt = self._build_prompt(room_id, room_name, messages, existing_profiles)
        raw = self._call_model(prompt)
        data = self._parse_json(raw)
        return self._normalize_result(data)

    def _call_model(self, prompt: str) -> str:
        for method_name in ("reply_text", "complete", "ask"):
            method = getattr(self.model, method_name, None)
            if callable(method):
                return str(method(prompt) or "")
        call = getattr(self.model, "call", None)
        if callable(call):
            from agent.protocol.models import LLMRequest

            response = call(LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                metadata={"source": "wechat-group-profile-evolution"},
            ))
            _raise_if_model_error(response)
            return _extract_model_text(response)
        if callable(self.model):
            return str(self.model(prompt) or "")
        raise ValueError("model does not expose a supported text completion method")

    @staticmethod
    def _build_prompt(
        room_id: str,
        room_name: str,
        messages: List[Dict[str, Any]],
        existing_profiles: List[Dict[str, Any]],
    ) -> str:
        lines = [
            "You are a WeChat group member profile extractor.",
            "Use only the current room evidence. Return JSON only.",
            "Identify members only by the opaque member_token shown in this batch.",
            "Never invent or transform a member_token.",
            "Every alias, role hint, interest, style, common term, and catchphrase must include confidence and evidence_message_ids.",
            "Do not infer real-world identity. Do not output local paths, XML, base64, or raw payloads.",
            "",
            "<current-room>",
            f"room_name: {room_name}",
            "</current-room>",
            "",
            "<existing-profiles>",
            json.dumps(_sanitize_existing_profiles(existing_profiles), ensure_ascii=False),
            "</existing-profiles>",
            "",
            "<messages>",
        ]
        for item in messages or []:
            message_id = str(item.get("message_id") or "").strip()
            member_token = str(item.get("member_token") or "").strip()
            if not message_id or not _is_opaque_member_token(member_token):
                continue
            sender_name = _sanitize_message_text(item.get("sender_nickname"))[:80]
            message_type = project_wechat_message_type(
                item.get("message_type") or "text",
                item.get("text"),
            )
            if message_type != "text":
                text = f"[{message_type}]"
            else:
                text = _sanitize_message_text(item.get("text"))
            mentioned_tokens = [
                str(token or "").strip()
                for token in item.get("mentioned_member_tokens") or []
                if _is_opaque_member_token(token)
            ]
            mention_suffix = " mentions={}".format(",".join(mentioned_tokens)) if mentioned_tokens else ""
            lines.append(f"[{message_id}] {sender_name}({member_token}){mention_suffix}: {text}")
        lines.extend([
            "</messages>",
            "",
            "Return schema:",
            '{"profiles":[{"member_token":"member_001","aliases":[{"value":"","confidence":0.0,"evidence_message_ids":[]}],"role_hints":[{"value":"","confidence":0.0,"evidence_message_ids":[]}],"interests":[{"value":"","confidence":0.0,"evidence_message_ids":[]}],"speak_style":{"value":"","confidence":0.0,"evidence_message_ids":[]},"common_terms":[{"value":"","confidence":0.0,"evidence_message_ids":[]}],"catchphrases":[{"value":"","confidence":0.0,"evidence_message_ids":[]}],"confidence":0.0}]}',
        ])
        return "\n".join(lines)

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        text = str(raw or "").strip()
        if not text:
            raise ValueError("empty LLM profile extraction response")
        try:
            parsed = json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                raise ValueError("LLM profile extraction response is not JSON")
            parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise ValueError("LLM profile extraction response must be a JSON object")
        return parsed

    @staticmethod
    def _normalize_result(data: Dict[str, Any]) -> Dict[str, Any]:
        profiles = []
        for raw_profile in data.get("profiles") or []:
            if not isinstance(raw_profile, dict):
                continue
            member_token = str(raw_profile.get("member_token") or "").strip()
            if not _is_opaque_member_token(member_token):
                continue
            profile = dict(raw_profile)
            profile.pop("sender_id", None)
            profile.pop("stable_member_id", None)
            profile["member_token"] = member_token
            profile["aliases"] = _filter_evidence_items(profile.get("aliases"))
            profile["role_hints"] = _filter_evidence_items(profile.get("role_hints"))
            profile["interests"] = _filter_evidence_items(profile.get("interests"))
            profile["common_terms"] = _filter_evidence_items(profile.get("common_terms"))
            profile["catchphrases"] = _filter_evidence_items(profile.get("catchphrases"))
            speak_style = profile.get("speak_style")
            if isinstance(speak_style, dict) and not _has_evidence(speak_style):
                profile["speak_style"] = {}
            profiles.append(profile)
        return {"profiles": profiles}


def _filter_evidence_items(value: Any) -> List[Any]:
    result = []
    for item in value or []:
        if isinstance(item, dict):
            if _has_evidence(item):
                result.append(item)
    return result


def _has_evidence(item: Dict[str, Any]) -> bool:
    return bool(_normalize_string_list(item.get("evidence_message_ids")))


def _sanitize_message_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"<[^>]{0,200}>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:600]


def _sanitize_existing_profiles(value: Any) -> List[Dict[str, Any]]:
    result = []
    allowed_fields = (
        "member_token",
        "primary_nickname",
        "aliases",
        "role_hints",
        "speak_style",
        "interests",
        "common_words",
    )
    for raw in value or []:
        if not isinstance(raw, dict):
            continue
        token = str(raw.get("member_token") or "").strip()
        if not _is_opaque_member_token(token):
            continue
        result.append({key: raw.get(key) for key in allowed_fields if key in raw})
    return result


def _is_opaque_member_token(value: Any) -> bool:
    return bool(re.fullmatch(r"member_[0-9]{3,6}", str(value or "").strip()))


def _normalize_string_list(value: Any) -> List[str]:
    if value is None:
        items = []
    elif isinstance(value, list):
        items = value
    else:
        items = str(value).replace("\n", ",").split(",")
    result = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _raise_if_model_error(response: Any) -> None:
    if not isinstance(response, dict) or not response.get("error"):
        return
    status_code = int(response.get("status_code") or 0)
    raw_message = str(response.get("message") or "LLM provider returned an error").strip()
    if status_code in _TRANSIENT_LLM_STATUS_CODES:
        message = "LLM provider temporarily unavailable"
        transient = True
    else:
        message = "LLM provider error"
        transient = False
    if status_code:
        message = "{} (HTTP {}): {}".format(message, status_code, raw_message)
    else:
        message = "{}: {}".format(message, raw_message)
    raise WechatGroupProfileExtractionError(
        message,
        status_code=status_code,
        transient=transient,
    )


def _extract_model_text(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("content", "text", "answer", "message"):
            value = response.get(key)
            text = _extract_model_text(value)
            if text:
                return text
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            return _extract_model_text(choices[0])
        return ""
    if isinstance(response, list):
        parts = []
        for item in response:
            text = _extract_model_text(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    for attr in ("content", "text", "answer"):
        if hasattr(response, attr):
            text = _extract_model_text(getattr(response, attr))
            if text:
                return text
    return str(response or "")
