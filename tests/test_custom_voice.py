# encoding:utf-8
import base64
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from bridge.reply import ReplyType
from common.log import logger
from voice.custom.custom_voice import (
    ASR_REQUEST_TIMEOUT,
    TTS_REQUEST_TIMEOUT,
    CustomVoice,
)


class TestCustomVoice(unittest.TestCase):
    def setUp(self):
        self.provider = {
            "id": "voice01",
            "api_key": "secret-key",
            "api_base": "https://voice.example/v1",
        }

    def test_voice_to_text_uses_custom_provider_and_explicit_model(self):
        response = Mock(status_code=200)
        response.json.return_value = {"text": "Hello, world"}

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            audio_file.write(b"RIFFtestWAVE")
            audio_path = audio_file.name
        try:
            with patch(
                "voice.custom.custom_voice.resolve_custom_provider_config",
                return_value=self.provider,
            ), patch(
                "voice.custom.custom_voice.conf",
                return_value={"voice_to_text_model": "TeleAI/TeleSpeechASR"},
            ), patch(
                "voice.custom.custom_voice.requests.post",
                return_value=response,
            ) as post:
                reply = CustomVoice("custom:voice01").voiceToText(audio_path)

            self.assertEqual(ReplyType.TEXT, reply.type)
            self.assertEqual("Hello, world", reply.content)
            args, kwargs = post.call_args
            self.assertEqual(
                "https://voice.example/v1/audio/transcriptions", args[0]
            )
            self.assertEqual(
                "Bearer secret-key", kwargs["headers"]["Authorization"]
            )
            self.assertEqual(
                {"model": "TeleAI/TeleSpeechASR"}, kwargs["data"]
            )
            self.assertEqual(ASR_REQUEST_TIMEOUT, kwargs["timeout"])
            self.assertEqual(os.path.basename(audio_path), kwargs["files"]["file"][0])
        finally:
            os.remove(audio_path)

    def test_api_error_log_redacts_custom_credentials(self):
        response = Mock(status_code=401)
        response.json.return_value = {
            "error": {
                "type": "auth_error",
                "message": "secret-key https://voice.example/v1",
            }
        }

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            audio_path = audio_file.name
        try:
            with patch(
                "voice.custom.custom_voice.resolve_custom_provider_config",
                return_value=self.provider,
            ), patch(
                "voice.custom.custom_voice.conf",
                return_value={"voice_to_text_model": "TeleAI/TeleSpeechASR"},
            ), patch(
                "voice.custom.custom_voice.requests.post",
                return_value=response,
            ), self.assertLogs(logger, level="ERROR") as logs:
                reply = CustomVoice("custom:voice01").voiceToText(audio_path)

            output = "\n".join(logs.output)
            self.assertEqual(ReplyType.ERROR, reply.type)
            self.assertNotIn("secret-key", output)
            self.assertNotIn("https://voice.example/v1", output)
            self.assertIn("[REDACTED]", output)
        finally:
            os.remove(audio_path)

    def test_standard_text_to_voice_uses_audio_speech_endpoint(self):
        response = Mock(
            status_code=200,
            content=b"ID3audio",
            headers={"Content-Type": "audio/mpeg"},
        )

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "voice.custom.custom_voice.resolve_custom_provider_config",
            return_value=self.provider,
        ), patch(
            "voice.custom.custom_voice.conf",
            return_value={
                "text_to_voice_model": "tts-1",
                "tts_voice_id": "alloy",
            },
        ), patch(
            "voice.custom.custom_voice.TmpDir"
        ) as tmp_dir_factory, patch(
            "voice.custom.custom_voice.requests.post",
            return_value=response,
        ) as post:
            tmp_dir_factory.return_value.path.return_value = tmp_dir

            reply = CustomVoice("custom:voice01").textToVoice("hello")

            self.assertEqual(ReplyType.VOICE, reply.type)
            self.assertTrue(os.path.isfile(reply.content))
            with open(reply.content, "rb") as audio_file:
                self.assertEqual(b"ID3audio", audio_file.read())
            args, kwargs = post.call_args
            self.assertEqual("https://voice.example/v1/audio/speech", args[0])
            self.assertEqual(
                {
                    "model": "tts-1",
                    "input": "hello",
                    "voice": "alloy",
                    "response_format": "mp3",
                },
                kwargs["json"],
            )
            self.assertEqual(TTS_REQUEST_TIMEOUT, kwargs["timeout"])

    def test_mimo_text_to_voice_uses_chat_completions_audio_contract(self):
        wav_bytes = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"audio"
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [
                {"message": {"audio": {"data": base64.b64encode(wav_bytes).decode()}}}
            ]
        }

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "voice.custom.custom_voice.resolve_custom_provider_config",
            return_value=self.provider,
        ), patch(
            "voice.custom.custom_voice.conf",
            return_value={
                "text_to_voice_model": "mimo-v2.5-tts",
                "tts_voice_id": "冰糖",
            },
        ), patch(
            "voice.custom.custom_voice.TmpDir"
        ) as tmp_dir_factory, patch(
            "voice.custom.custom_voice.requests.post",
            return_value=response,
        ) as post:
            tmp_dir_factory.return_value.path.return_value = tmp_dir

            reply = CustomVoice("custom:voice01").textToVoice("你好")

            self.assertEqual(ReplyType.VOICE, reply.type)
            self.assertTrue(os.path.isfile(reply.content))
            with open(reply.content, "rb") as audio_file:
                self.assertEqual(wav_bytes, audio_file.read())
            args, kwargs = post.call_args
            self.assertEqual("https://voice.example/v1/chat/completions", args[0])
            self.assertEqual(
                {
                    "model": "mimo-v2.5-tts",
                    "messages": [{"role": "assistant", "content": "你好"}],
                    "audio": {"format": "wav", "voice": "冰糖"},
                },
                kwargs["json"],
            )
            self.assertEqual(TTS_REQUEST_TIMEOUT, kwargs["timeout"])

    def test_standard_text_to_voice_rejects_json_error_with_http_200(self):
        response = Mock(
            status_code=200,
            content=b'{"error":{"message":"secret-key https://voice.example/v1"}}',
            headers={"Content-Type": "application/json"},
        )
        response.json.return_value = {
            "error": {"message": "secret-key https://voice.example/v1"}
        }

        with patch(
            "voice.custom.custom_voice.resolve_custom_provider_config",
            return_value=self.provider,
        ), patch(
            "voice.custom.custom_voice.conf",
            return_value={"text_to_voice_model": "tts-1"},
        ), patch(
            "voice.custom.custom_voice.requests.post",
            return_value=response,
        ), patch.object(
            CustomVoice, "_write_audio"
        ) as write_audio, self.assertLogs(logger, level="ERROR") as logs:
            reply = CustomVoice("custom:voice01").textToVoice("hello")

        output = "\n".join(logs.output)
        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertNotIn("secret-key", output)
        self.assertNotIn("https://voice.example/v1", output)
        self.assertIn("[REDACTED]", output)
        write_audio.assert_not_called()


if __name__ == "__main__":
    unittest.main()
