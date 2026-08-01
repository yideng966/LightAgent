# encoding:utf-8
"""按已保存厂商配置获取远端模型目录。"""

import json
from typing import Dict, List
from urllib.parse import urlparse

import requests

from agent.tools.utils.url_safety import validate_url_safe


MAX_PAGES = 5
MAX_MODELS = 1000
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT = (5, 10)


class ModelCatalogError(Exception):
    """可安全返回给 Web 控制台的模型目录错误。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ModelCatalogService:
    """使用厂商凭据调用 Models API，并归一化返回值。"""

    _PROTOCOLS = {
        "claudeAPI": "anthropic",
        "gemini": "gemini",
    }
    _RUNTIME_BASE_FIELDS = {
        "minimax": "minimax_api_base",
        "linkai": "linkai_api_base",
    }
    _RUNTIME_DEFAULT_BASES = {
        "minimax": "https://api.minimaxi.com/v1",
        "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "linkai": "https://api.link-ai.tech/v1",
    }

    def __init__(self, local_config: dict, provider_meta: Dict[str, dict]):
        self._config = local_config or {}
        self._provider_meta = provider_meta or {}
        proxy = str(self._config.get("proxy") or "").strip()
        self._proxies = {"http": proxy, "https": proxy} if proxy else None

    def fetch(self, provider_id: str) -> List[dict]:
        provider = self._resolve_provider(str(provider_id or "").strip())
        protocol = provider["protocol"]
        if protocol == "anthropic":
            models = self._fetch_anthropic(provider)
        elif protocol == "gemini":
            models = self._fetch_gemini(provider)
        else:
            models = self._fetch_openai_compatible(provider)
        models = self._deduplicate(models)
        if not models:
            raise ModelCatalogError("models_api_empty")
        return models[:MAX_MODELS]

    def _resolve_provider(self, provider_id: str) -> dict:
        if provider_id.startswith("custom:"):
            custom_id = provider_id.split(":", 1)[1]
            raw = next(
                (
                    item for item in self._config.get("custom_providers", [])
                    if isinstance(item, dict) and item.get("id") == custom_id
                ),
                None,
            )
            if raw is None:
                raise ModelCatalogError("provider_not_found")
            api_base = str(raw.get("api_base") or "").strip()
            if not api_base:
                raise ModelCatalogError("provider_not_configured")
            return {
                "id": provider_id,
                "protocol": "openai",
                "api_key": str(raw.get("api_key") or "").strip(),
                "api_base": api_base,
            }

        meta = self._provider_meta.get(provider_id)
        if not meta:
            raise ModelCatalogError("provider_not_found")

        key_field = meta.get("api_key_field")
        api_key = str(self._config.get(key_field) or "").strip() if key_field else ""
        if not self._is_real_key(api_key):
            raise ModelCatalogError("provider_not_configured")

        base_field = (
            meta.get("api_base_key")
            or self._RUNTIME_BASE_FIELDS.get(provider_id)
        )
        api_base = str(self._config.get(base_field) or "").strip() if base_field else ""
        if not api_base:
            api_base = str(
                meta.get("api_base_default")
                or self._RUNTIME_DEFAULT_BASES.get(provider_id)
                or ""
            ).strip()
        if not api_base:
            raise ModelCatalogError("models_api_unsupported")

        return {
            "id": provider_id,
            "protocol": self._PROTOCOLS.get(provider_id, "openai"),
            "api_key": api_key,
            "api_base": api_base,
        }

    @staticmethod
    def _is_real_key(value: str) -> bool:
        return bool(value) and value not in ("YOUR API KEY", "YOUR_API_KEY")

    def _fetch_openai_compatible(self, provider: dict) -> List[dict]:
        url = self._models_url(provider["api_base"], "openai")
        headers = {"Accept": "application/json"}
        if provider["api_key"]:
            headers["Authorization"] = f"Bearer {provider['api_key']}"
        payload = self._request_json(url, headers=headers)
        data = payload.get("data")
        if not isinstance(data, list):
            raise ModelCatalogError("models_api_invalid_response")
        return [self._normalize_openai_item(item) for item in data]

    def _fetch_anthropic(self, provider: dict) -> List[dict]:
        url = self._models_url(provider["api_base"], "anthropic")
        headers = {
            "Accept": "application/json",
            "x-api-key": provider["api_key"],
            "anthropic-version": "2023-06-01",
        }
        params = {"limit": 100}
        models = []
        seen_cursors = set()
        for _ in range(MAX_PAGES):
            payload = self._request_json(url, headers=headers, params=params)
            data = payload.get("data")
            if not isinstance(data, list):
                raise ModelCatalogError("models_api_invalid_response")
            models.extend(self._normalize_anthropic_item(item) for item in data)
            if len(models) >= MAX_MODELS or not payload.get("has_more"):
                break
            cursor = str(payload.get("last_id") or "").strip()
            if not cursor or cursor in seen_cursors:
                raise ModelCatalogError("models_api_invalid_response")
            seen_cursors.add(cursor)
            params = {"limit": 100, "after_id": cursor}
        return models

    def _fetch_gemini(self, provider: dict) -> List[dict]:
        url = self._models_url(provider["api_base"], "gemini")
        headers = {
            "Accept": "application/json",
            "x-goog-api-key": provider["api_key"],
        }
        params = {"pageSize": 1000}
        models = []
        seen_tokens = set()
        for _ in range(MAX_PAGES):
            payload = self._request_json(url, headers=headers, params=params)
            data = payload.get("models")
            if not isinstance(data, list):
                raise ModelCatalogError("models_api_invalid_response")
            models.extend(self._normalize_gemini_item(item) for item in data)
            if len(models) >= MAX_MODELS:
                break
            token = str(payload.get("nextPageToken") or "").strip()
            if not token:
                break
            if token in seen_tokens:
                raise ModelCatalogError("models_api_invalid_response")
            seen_tokens.add(token)
            params = {"pageSize": 1000, "pageToken": token}
        return models

    def _request_json(self, url: str, headers: dict, params=None) -> dict:
        self._validate_target(url)
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
                proxies=self._proxies,
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout as exc:
            raise ModelCatalogError("models_api_timeout") from exc
        except requests.RequestException as exc:
            raise ModelCatalogError("models_api_unavailable") from exc

        self._raise_for_status(response.status_code)
        raw = bytearray()
        try:
            content_length = int(response.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            content_length = 0
        if content_length > MAX_RESPONSE_BYTES:
            raise ModelCatalogError("models_api_invalid_response")
        try:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ModelCatalogError("models_api_invalid_response")
            payload = json.loads(bytes(raw).decode("utf-8-sig"))
        except ModelCatalogError:
            raise
        except requests.RequestException as exc:
            raise ModelCatalogError("models_api_unavailable") from exc
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ModelCatalogError("models_api_invalid_response") from exc
        if not isinstance(payload, dict):
            raise ModelCatalogError("models_api_invalid_response")
        return payload

    @staticmethod
    def _raise_for_status(status_code: int) -> None:
        if 200 <= status_code < 300:
            return
        if status_code in (401, 403):
            raise ModelCatalogError("models_api_unauthorized")
        if status_code in (404, 405):
            raise ModelCatalogError("models_api_unsupported")
        if status_code in (408, 429) or status_code >= 500:
            raise ModelCatalogError("models_api_unavailable")
        raise ModelCatalogError("models_api_invalid_response")

    @staticmethod
    def _models_url(api_base: str, protocol: str) -> str:
        base = str(api_base or "").rstrip("/")
        if protocol == "gemini" and not base.endswith(("/v1", "/v1beta")):
            base = f"{base}/v1beta"
        return f"{base}/models"

    @staticmethod
    def _validate_target(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ModelCatalogError("provider_not_configured")
        if parsed.username or parsed.password:
            raise ModelCatalogError("provider_not_configured")
        try:
            validate_url_safe(url)
        except ValueError as exc:
            raise ModelCatalogError("models_api_unavailable") from exc

    @staticmethod
    def _normalize_openai_item(item) -> dict:
        if not isinstance(item, dict):
            return {}
        return ModelCatalogService._model_entry(item.get("id"))

    @staticmethod
    def _normalize_anthropic_item(item) -> dict:
        if not isinstance(item, dict):
            return {}
        return ModelCatalogService._model_entry(
            item.get("id"),
            hint=item.get("display_name"),
        )

    @staticmethod
    def _normalize_gemini_item(item) -> dict:
        if not isinstance(item, dict):
            return {}
        model_id = str(item.get("name") or "")
        if model_id.startswith("models/"):
            model_id = model_id[7:]
        capabilities = (
            item.get("supportedGenerationMethods")
            or item.get("supportedActions")
            or []
        )
        return ModelCatalogService._model_entry(
            model_id,
            hint=item.get("displayName"),
            capabilities=capabilities,
        )

    @staticmethod
    def _model_entry(model_id, hint=None, capabilities=None) -> dict:
        value = str(model_id or "").strip()
        if not value or len(value) > 512:
            return {}
        hint_value = str(hint or "").strip()
        if hint_value == value:
            hint_value = ""
        normalized_capabilities = []
        if isinstance(capabilities, list):
            normalized_capabilities = [
                str(item).strip()[:128]
                for item in capabilities[:32]
                if str(item).strip()
            ]
        return {
            "id": value,
            "label": value,
            "hint": hint_value[:256],
            "capabilities": normalized_capabilities,
        }

    @staticmethod
    def _deduplicate(models: List[dict]) -> List[dict]:
        result = []
        seen = set()
        for item in models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            if not model_id or model_id in seen:
                continue
            seen.add(model_id)
            result.append(item)
            if len(result) >= MAX_MODELS:
                break
        return result
