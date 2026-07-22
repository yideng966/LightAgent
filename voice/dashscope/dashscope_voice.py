# encoding:utf-8
"""DashScope voice: qwen3-asr-flash (ASR) + qwen3-tts-flash (TTS)
via dashscope.MultiModalConversation."""
import datetime
import os
import random
from typing import Optional

import dashscope
import requests
from dashscope import MultiModalConversation

from bridge.reply import Reply, ReplyType
from common.log import logger
from common.tmp_dir import TmpDir
from config import conf
from voice import audio_convert
from voice.voice import Voice


DEFAULT_ASR_MODEL = "qwen3-asr-flash"
DEFAULT_TTS_MODEL = "qwen3-tts-flash"
DEFAULT_TTS_VOICE = "Cherry"
MAX_DURATION_SECONDS = 300
MAX_FILE_BYTES = 10 * 1024 * 1024


class DashScopeVoice(Voice):
    def __init__(self):
        pass

    def voiceToText(self, voice_file: str):
        try:
            voice_file = self._ensure_compatible_format(voice_file)

            try:
                size = os.path.getsize(voice_file)
                if size > MAX_FILE_BYTES:
                    logger.warning(
                        f"[DashScopeVoice] audio file {size}B exceeds {MAX_FILE_BYTES}B; "
                        f"qwen3-asr-flash may reject it"
                    )
            except OSError:
                pass

            api_key = conf().get("dashscope_api_key", "")
            if not api_key:
                logger.error("[DashScopeVoice] dashscope_api_key is not configured")
                return Reply(ReplyType.ERROR, "未配置 DashScope API key")
            dashscope.api_key = api_key

            model = conf().get("voice_to_text_model") or DEFAULT_ASR_MODEL
            abs_path = os.path.abspath(voice_file)
            file_uri = f"file://{abs_path}"

            messages = [
                {"role": "user", "content": [{"audio": file_uri}]},
            ]
            response = MultiModalConversation.call(
                model=model,
                messages=messages,
                result_format="message",
                asr_options={"enable_itn": False, "enable_lid": True},
            )

            text = self._extract_text(response)
            if text is None:
                logger.error(f"[DashScopeVoice] voiceToText failed: {response}")
                return Reply(ReplyType.ERROR, "我暂时还无法听清您的语音，请稍后再试吧~")

            logger.info(f"[DashScopeVoice] voiceToText model={model} text={text}")
            return Reply(ReplyType.TEXT, text)
        except Exception as e:
            logger.exception(f"[DashScopeVoice] voiceToText exception: {e}")
            return Reply(ReplyType.ERROR, "我暂时还无法听清您的语音，请稍后再试吧~")

    def textToVoice(self, text: str):
        try:
            api_key = conf().get("dashscope_api_key", "")
            if not api_key:
                logger.error("[DashScopeVoice] dashscope_api_key is not configured")
                return Reply(ReplyType.ERROR, "未配置 DashScope API key")
            dashscope.api_key = api_key

            model = conf().get("text_to_voice_model") or DEFAULT_TTS_MODEL
            voice = conf().get("tts_voice_id") or DEFAULT_TTS_VOICE
            response = MultiModalConversation.call(
                model=model,
                api_key=api_key,
                text=text,
                voice=voice,
                stream=False,
            )

            url = self._extract_audio_url(response)
            if not url:
                logger.error(f"[DashScopeVoice] textToVoice failed: {response}")
                return Reply(ReplyType.ERROR, "语音合成失败")

            local_path = self._download_audio(url)
            if not local_path:
                return Reply(ReplyType.ERROR, "语音合成失败")

            logger.info(f"[DashScopeVoice] textToVoice model={model} voice={voice} file={local_path}")
            return Reply(ReplyType.VOICE, local_path)
        except Exception as e:
            logger.exception(f"[DashScopeVoice] textToVoice exception: {e}")
            return Reply(ReplyType.ERROR, "语音合成失败")

    @staticmethod
    def _extract_audio_url(response) -> Optional[str]:
        try:
            if getattr(response, "status_code", 200) != 200:
                return None
            audio = response.output.get("audio") if response.output else None
            if isinstance(audio, dict):
                return audio.get("url") or None
            return getattr(audio, "url", None)
        except Exception:
            return None

    @staticmethod
    def _download_audio(url: str) -> Optional[str]:
        try:
            tmp_dir = TmpDir().path()
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            ext = os.path.splitext(url.split("?", 1)[0])[1].lower() or ".wav"
            if ext not in (".mp3", ".wav", ".m4a", ".aac", ".opus"):
                ext = ".wav"
            dst = os.path.join(tmp_dir, f"dashscope_tts_{ts}_{random.randint(0, 9999)}{ext}")
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            with open(dst, "wb") as f:
                f.write(resp.content)
            return dst
        except Exception as e:
            logger.error(f"[DashScopeVoice] download audio failed: {e}")
            return None

    @staticmethod
    def _ensure_compatible_format(voice_file: str) -> str:
        # qwen3-asr-flash doesn't accept AMR/SILK; mp3/wav/m4a/aac/opus pass through.
        lower = voice_file.lower()
        if lower.endswith(".amr") or lower.endswith(".silk") or lower.endswith(".slk"):
            try:
                mp3_file = os.path.splitext(voice_file)[0] + ".mp3"
                audio_convert.any_to_mp3(voice_file, mp3_file)
                return mp3_file
            except Exception as e:
                logger.warning(f"[DashScopeVoice] mp3 convert failed: {e}")
        return voice_file

    @staticmethod
    def _extract_text(response) -> Optional[str]:
        try:
            if getattr(response, "status_code", 200) != 200:
                return None
            choices = response.output.get("choices") or []
            if not choices:
                return None
            content = choices[0].get("message", {}).get("content")
            if isinstance(content, str):
                return content.strip() or None
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(item["text"])
                    elif isinstance(item, str):
                        parts.append(item)
                text = "".join(parts).strip()
                return text or None
            return None
        except Exception:
            return None
