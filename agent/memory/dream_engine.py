"""Shared stateless LLM engine for memory summarization and distillation."""

from __future__ import annotations

import re
from typing import Any, Optional


_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_STATUS_PATTERN = re.compile(r"(?<!\d)(408|429|500|502|503|504)(?!\d)")
_TRANSIENT_TEXT_PATTERN = re.compile(
    r"(?i)(?:timeout|timed out|rate limit|too many requests|temporarily unavailable|service unavailable|overloaded)"
)


class MemoryDreamError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 0, transient: bool = False):
        super().__init__(message)
        self.status_code = int(status_code or 0)
        self.transient = bool(transient)


class MemoryDreamEngine:
    def __init__(self, text_model_router: Optional[Any] = None):
        if text_model_router is None:
            from bridge.bridge import Bridge

            text_model_router = Bridge().get_text_model_router()
        self.text_model_router = text_model_router

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        purpose: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        complete = getattr(self.text_model_router, "complete", None)
        if not callable(complete):
            raise MemoryDreamError("shared text model router does not support complete()")
        try:
            response = complete(
                [{"role": "user", "content": str(user_prompt or "")}],
                purpose=str(purpose or "memory_dream"),
                system=str(system_prompt or ""),
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except MemoryDreamError:
            raise
        except Exception as exc:
            status_code = _status_code_from_value(exc)
            transient = status_code in _TRANSIENT_STATUS_CODES or bool(
                _TRANSIENT_TEXT_PATTERN.search(str(exc or ""))
            )
            raise MemoryDreamError(
                _format_error(str(exc), status_code),
                status_code=status_code,
                transient=transient,
            ) from exc

        raw = {}
        if isinstance(response, dict):
            raw = response.get("raw") if isinstance(response.get("raw"), dict) else {}
            status_code = _first_status_code(response, raw)
            success = response.get("success") is not False and not response.get("error")
            if raw.get("error"):
                success = False
            content = str(
                response.get("content")
                or response.get("text")
                or raw.get("message")
                or ""
            ).strip()
            if not success and (
                content
                or response.get("error")
                or raw.get("error")
                or status_code
            ):
                transient = status_code in _TRANSIENT_STATUS_CODES or bool(
                    _TRANSIENT_TEXT_PATTERN.search(content)
                )
                raise MemoryDreamError(
                    _format_error(content or "text model completion failed", status_code),
                    status_code=status_code,
                    transient=transient,
                )
        else:
            content = str(response or "").strip()

        if not content:
            raise MemoryDreamError(_empty_completion_reason(raw))
        return content


def _first_status_code(*values: Any) -> int:
    for value in values:
        if not isinstance(value, dict):
            continue
        for key in ("status_code", "status"):
            try:
                code = int(value.get(key) or 0)
            except Exception:
                code = 0
            if code:
                return code
    for value in values:
        code = _status_code_from_value(value)
        if code:
            return code
    return 0


def _status_code_from_value(value: Any) -> int:
    match = _STATUS_PATTERN.search(str(value or ""))
    return int(match.group(1)) if match else 0


def _format_error(message: str, status_code: int) -> str:
    text = str(message or "text model completion failed").strip()
    return f"memory dream model error (HTTP {status_code}): {text}" if status_code else f"memory dream model error: {text}"


def _empty_completion_reason(raw: Any) -> str:
    base = "text model completion returned empty content"
    if not isinstance(raw, dict):
        return base

    def safe_value(value: Any, limit: int = 80) -> str:
        if not isinstance(value, (str, int, float)):
            return ""
        return " ".join(str(value).split())[:limit]

    details = []
    model = safe_value(raw.get("model"))
    if model:
        details.append(f"model={model}")

    choices = raw.get("choices") or []
    first = choices[0] if choices and isinstance(choices[0], dict) else {}
    finish_reason = safe_value(first.get("finish_reason"))
    if finish_reason:
        details.append(f"finish_reason={finish_reason}")

    usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
    completion_tokens = safe_value(usage.get("completion_tokens"))
    if completion_tokens:
        details.append(f"completion_tokens={completion_tokens}")
    token_details = (
        usage.get("completion_tokens_details")
        if isinstance(usage.get("completion_tokens_details"), dict)
        else {}
    )
    reasoning_tokens = safe_value(token_details.get("reasoning_tokens"))
    if reasoning_tokens:
        details.append(f"reasoning_tokens={reasoning_tokens}")

    return f"{base} ({', '.join(details)})" if details else base
