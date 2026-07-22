# encoding:utf-8
"""Voice adapter for user-defined OpenAI-compatible providers."""

import base64
import binascii
import os
import uuid

import requests

from bridge.reply import Reply, ReplyType
from common.log import logger
from common.tmp_dir import TmpDir
from config import conf
from models.custom_provider import resolve_custom_provider_config
from voice.voice import Voice


ASR_REQUEST_TIMEOUT = (5, 90)
TTS_REQUEST_TIMEOUT = (5, 120)
ASR_ERROR_MESSAGE = "我暂时还无法听清您的语音，请稍后再试吧~"
TTS_ERROR_MESSAGE = "语音合成失败，请稍后再试"
MIMO_TTS_MODEL_PREFIX = "mimo-v2.5-tts"
MIMO_DEFAULT_VOICE = "冰糖"
OPENAI_DEFAULT_VOICE = "alloy"


class CustomVoice(Voice):
    def __init__(self, provider_type: str):
        self.provider_type = provider_type

    def voiceToText(self, voice_file: str):
        resolved = self._resolve_provider("voice_to_text_model")
        if resolved is None:
            return Reply(ReplyType.ERROR, ASR_ERROR_MESSAGE)
        api_key, api_base, model = resolved

        try:
            with open(voice_file, "rb") as audio_file:
                response = requests.post(
                    f"{api_base}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={
                        "file": (
                            os.path.basename(voice_file),
                            audio_file,
                            "application/octet-stream",
                        )
                    },
                    data={"model": model},
                    timeout=ASR_REQUEST_TIMEOUT,
                )
        except (OSError, requests.RequestException) as exc:
            self._log_request_failure("voice_to_text", model, exc)
            return Reply(ReplyType.ERROR, ASR_ERROR_MESSAGE)

        payload = self._json_payload(response, "voice_to_text", model)
        if payload is None:
            return Reply(ReplyType.ERROR, ASR_ERROR_MESSAGE)
        if response.status_code != 200:
            self._log_api_failure(
                "voice_to_text", model, response.status_code, payload, api_key, api_base
            )
            return Reply(ReplyType.ERROR, ASR_ERROR_MESSAGE)

        text = (payload.get("text") or "").strip() if isinstance(payload, dict) else ""
        if not text:
            logger.error(
                "[CustomVoice] empty transcription: provider=%s model=%s",
                self.provider_type,
                model,
            )
            return Reply(ReplyType.ERROR, ASR_ERROR_MESSAGE)

        logger.info(
            "[CustomVoice] transcription succeeded: provider=%s model=%s text_length=%s",
            self.provider_type,
            model,
            len(text),
        )
        return Reply(ReplyType.TEXT, text)

    def textToVoice(self, text: str):
        resolved = self._resolve_provider("text_to_voice_model")
        if resolved is None:
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)
        api_key, api_base, model = resolved

        if model.lower().startswith(MIMO_TTS_MODEL_PREFIX):
            return self._mimo_text_to_voice(text, api_key, api_base, model)
        return self._openai_text_to_voice(text, api_key, api_base, model)

    def _mimo_text_to_voice(
        self, text: str, api_key: str, api_base: str, model: str
    ) -> Reply:
        voice_id = (conf().get("tts_voice_id") or MIMO_DEFAULT_VOICE).strip()
        try:
            response = requests.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "assistant", "content": text}],
                    "audio": {"format": "wav", "voice": voice_id},
                },
                timeout=TTS_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            self._log_request_failure("text_to_voice", model, exc)
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)

        payload = self._json_payload(response, "text_to_voice", model)
        if payload is None:
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)
        if (
            response.status_code != 200
            or not isinstance(payload, dict)
            or payload.get("error")
        ):
            self._log_api_failure(
                "text_to_voice",
                model,
                response.status_code,
                payload,
                api_key,
                api_base,
            )
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)

        try:
            message = (payload.get("choices") or [{}])[0].get("message") or {}
            audio_data = (message.get("audio") or {}).get("data") or ""
            audio_bytes = base64.b64decode(audio_data, validate=True)
        except (AttributeError, binascii.Error, IndexError, TypeError, ValueError):
            audio_bytes = b""
        if not audio_bytes.startswith(b"RIFF") or audio_bytes[8:12] != b"WAVE":
            logger.error(
                "[CustomVoice] invalid MiMo audio response: provider=%s model=%s",
                self.provider_type,
                model,
            )
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)

        return self._write_audio(audio_bytes, "wav", model, voice_id)

    def _openai_text_to_voice(
        self, text: str, api_key: str, api_base: str, model: str
    ) -> Reply:
        voice_id = (conf().get("tts_voice_id") or OPENAI_DEFAULT_VOICE).strip()
        try:
            response = requests.post(
                f"{api_base}/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": text,
                    "voice": voice_id,
                    "response_format": "mp3",
                },
                timeout=TTS_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            self._log_request_failure("text_to_voice", model, exc)
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)

        if response.status_code != 200:
            payload = self._optional_json_payload(response)
            self._log_api_failure(
                "text_to_voice", model, response.status_code, payload, api_key, api_base
            )
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)

        payload = self._json_audio_error(response)
        if payload is not None:
            self._log_api_failure(
                "text_to_voice", model, response.status_code, payload, api_key, api_base
            )
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)

        audio_bytes = response.content or b""
        if not isinstance(audio_bytes, (bytes, bytearray)) or not audio_bytes:
            logger.error(
                "[CustomVoice] empty audio response: provider=%s model=%s",
                self.provider_type,
                model,
            )
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)
        return self._write_audio(bytes(audio_bytes), "mp3", model, voice_id)

    def _resolve_provider(self, model_key: str):
        provider = resolve_custom_provider_config(self.provider_type)
        if provider is None:
            logger.error(
                "[CustomVoice] provider not found: provider=%s",
                self.provider_type,
            )
            return None

        api_key = (provider.get("api_key") or "").strip()
        api_base = (provider.get("api_base") or "").strip().rstrip("/")
        model = (conf().get(model_key) or "").strip()
        missing = [
            name
            for name, value in (
                ("api_key", api_key),
                ("api_base", api_base),
                (model_key, model),
            )
            if not value
        ]
        if missing:
            logger.error(
                "[CustomVoice] missing configuration: provider=%s fields=%s",
                self.provider_type,
                ",".join(missing),
            )
            return None
        return api_key, api_base, model

    def _json_payload(self, response, capability: str, model: str):
        try:
            return response.json()
        except ValueError:
            logger.error(
                "[CustomVoice] invalid JSON response: provider=%s capability=%s model=%s status=%s",
                self.provider_type,
                capability,
                model,
                response.status_code,
            )
            return None

    @staticmethod
    def _optional_json_payload(response):
        try:
            return response.json()
        except ValueError:
            return {}

    @classmethod
    def _json_audio_error(cls, response):
        headers = getattr(response, "headers", None)
        content_type = ""
        if headers is not None and hasattr(headers, "get"):
            content_type = str(headers.get("Content-Type", "")).lower()
        content = getattr(response, "content", b"") or b""
        looks_like_json = "json" in content_type
        if isinstance(content, (bytes, bytearray)):
            looks_like_json = looks_like_json or content.lstrip()[:1] in (b"{", b"[")
        return cls._optional_json_payload(response) if looks_like_json else None

    def _write_audio(
        self, audio_bytes: bytes, extension: str, model: str, voice_id: str
    ) -> Reply:
        try:
            file_name = os.path.join(
                TmpDir().path(), f"custom_tts_{uuid.uuid4().hex}.{extension}"
            )
            with open(file_name, "wb") as audio_file:
                audio_file.write(audio_bytes)
        except OSError as exc:
            self._log_request_failure("text_to_voice", model, exc)
            return Reply(ReplyType.ERROR, TTS_ERROR_MESSAGE)

        logger.info(
            "[CustomVoice] synthesis succeeded: provider=%s model=%s voice=%s bytes=%s",
            self.provider_type,
            model,
            voice_id,
            len(audio_bytes),
        )
        return Reply(ReplyType.VOICE, file_name)

    def _log_request_failure(self, capability: str, model: str, exc: Exception):
        logger.error(
            "[CustomVoice] request failed: provider=%s capability=%s model=%s error_type=%s",
            self.provider_type,
            capability,
            model,
            type(exc).__name__,
        )

    def _log_api_failure(
        self,
        capability: str,
        model: str,
        status_code: int,
        payload,
        api_key: str,
        api_base: str,
    ):
        logger.error(
            "[CustomVoice] API failed: provider=%s capability=%s model=%s status=%s error=%s",
            self.provider_type,
            capability,
            model,
            status_code,
            self._safe_error_summary(payload, api_key, api_base),
        )

    @staticmethod
    def _safe_error_summary(payload, api_key: str, api_base: str) -> str:
        if not isinstance(payload, dict):
            return "invalid_payload"

        error = payload.get("error")
        if isinstance(error, dict):
            parts = [
                str(error.get("type") or ""),
                str(error.get("code") or ""),
                str(error.get("message") or ""),
            ]
            summary = " ".join(part for part in parts if part)
        elif error:
            summary = str(error)
        else:
            summary = str(payload.get("message") or "unknown_error")

        for secret in (api_key, api_base):
            if secret:
                summary = summary.replace(secret, "[REDACTED]")
        return summary[:300]
