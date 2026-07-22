# encoding:utf-8
import unittest
from unittest.mock import Mock, patch

from bridge.bridge import Bridge
from bridge.reply import Reply, ReplyType
from common.log import logger
from voice import factory


class TestVoiceFactory(unittest.TestCase):
    def test_factory_exposes_supported_asr_providers(self):
        expected = frozenset(
            {
                "baidu",
                "google",
                "openai",
                "azure",
                "linkai",
                "ali",
                "xunfei",
                "tencent",
                "dashscope",
                "zhipu",
                "zhipuai",
            }
        )

        self.assertIsInstance(factory.SUPPORTED_ASR_PROVIDERS, frozenset)
        self.assertEqual(expected, factory.SUPPORTED_ASR_PROVIDERS)

    def test_factory_exposes_supported_tts_providers(self):
        expected = frozenset(
            {
                "baidu",
                "google",
                "openai",
                "pytts",
                "azure",
                "elevenlabs",
                "linkai",
                "ali",
                "edge",
                "xunfei",
                "tencent",
                "minimax",
                "dashscope",
                "zhipu",
                "zhipuai",
                "mimo",
            }
        )

        self.assertIsInstance(factory.SUPPORTED_TTS_PROVIDERS, frozenset)
        self.assertEqual(expected, factory.SUPPORTED_TTS_PROVIDERS)

    def test_factory_raises_descriptive_error_for_unsupported_provider(self):
        self.assertTrue(
            hasattr(factory, "UnsupportedVoiceProviderError"),
            "voice.factory must expose UnsupportedVoiceProviderError",
        )
        self.assertTrue(
            issubclass(factory.UnsupportedVoiceProviderError, ValueError)
        )

        with self.assertRaises(factory.UnsupportedVoiceProviderError) as caught:
            factory.create_voice("custom:missing")

        self.assertEqual("custom:missing", caught.exception.voice_type)
        self.assertIn("custom:missing", str(caught.exception))

    def test_factory_creates_custom_voice_for_explicit_capabilities(self):
        from voice.custom.custom_voice import CustomVoice

        asr_voice = factory.create_voice(
            "custom:voice01", capability="voice_to_text"
        )
        tts_voice = factory.create_voice(
            "custom:voice01", capability="text_to_voice"
        )

        self.assertIsInstance(asr_voice, CustomVoice)
        self.assertIsInstance(tts_voice, CustomVoice)

    def test_bridge_returns_error_reply_for_unsupported_asr_provider(self):
        bridge = Bridge()
        sensitive_values = (
            "secret-api-key",
            "https://secret.example/v1",
        )
        unsupported_error = factory.UnsupportedVoiceProviderError("custom:missing")
        unsupported_error.args = (
            f"provider details: {sensitive_values[0]} {sensitive_values[1]}",
        )
        with patch.dict(bridge.btype, {"voice_to_text": "custom:missing"}), \
                patch.dict(bridge.bots, {"voice_to_text": None}), \
                patch(
                    "bridge.bridge.create_voice",
                    side_effect=unsupported_error,
                ) as create_voice:
            with self.assertLogs(logger, level="ERROR") as caught_logs:
                try:
                    reply = bridge.fetch_voice_to_text("voice.silk")
                except Exception as exc:
                    self.fail(
                        f"unsupported voice_to_text provider escaped Bridge: {exc!r}"
                    )

        create_voice.assert_called_once_with(
            "custom:missing", capability="voice_to_text"
        )
        log_output = "\n".join(caught_logs.output)
        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertIn("voice_to_text", reply.content)
        self.assertIn("custom:missing", reply.content)
        self.assertIn("voice_to_text", log_output)
        self.assertIn("custom:missing", log_output)
        for sensitive_value in sensitive_values:
            self.assertNotIn(sensitive_value, reply.content)
            self.assertNotIn(sensitive_value, log_output)

    def test_bridge_returns_error_reply_for_unsupported_tts_provider(self):
        bridge = Bridge()
        sensitive_values = (
            "secret-api-key",
            "https://secret.example/v1",
        )
        unsupported_error = factory.UnsupportedVoiceProviderError("custom:missing")
        unsupported_error.args = (
            f"provider details: {sensitive_values[0]} {sensitive_values[1]}",
        )
        with patch.dict(bridge.btype, {"text_to_voice": "custom:missing"}), \
                patch.dict(bridge.bots, {"text_to_voice": None}), \
                patch(
                    "bridge.bridge.create_voice",
                    side_effect=unsupported_error,
                ) as create_voice:
            with self.assertLogs(logger, level="ERROR") as caught_logs:
                try:
                    reply = bridge.fetch_text_to_voice("hello")
                except Exception as exc:
                    self.fail(
                        f"unsupported text_to_voice provider escaped Bridge: {exc!r}"
                    )

        create_voice.assert_called_once_with(
            "custom:missing", capability="text_to_voice"
        )
        log_output = "\n".join(caught_logs.output)
        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertIn("text_to_voice", reply.content)
        self.assertIn("custom:missing", reply.content)
        self.assertIn("text_to_voice", log_output)
        self.assertIn("custom:missing", log_output)
        for sensitive_value in sensitive_values:
            self.assertNotIn(sensitive_value, reply.content)
            self.assertNotIn(sensitive_value, log_output)

    def test_bridge_asr_recovers_after_custom_provider_is_fixed(self):
        from voice.custom.custom_voice import CustomVoice

        bridge = Bridge()
        with patch.dict(bridge.btype, {"voice_to_text": "custom:missing"}), \
                patch.dict(bridge.bots, {}, clear=True):
            reply = bridge.fetch_voice_to_text("voice.silk")

            self.assertEqual(ReplyType.ERROR, reply.type)
            self.assertIsInstance(bridge.bots["voice_to_text"], CustomVoice)

            expected_reply = Reply(ReplyType.TEXT, "transcribed")
            working_bot = Mock()
            working_bot.voiceToText.return_value = expected_reply
            bridge.bots["voice_to_text"] = Mock(name="stale_voice_to_text_bot")

            corrected_config = {
                "voice_to_text": "openai",
                "text_to_voice": "google",
                "use_linkai": False,
            }
            with patch("bridge.bridge.conf", return_value=corrected_config):
                bridge.refresh_voice()

            self.assertEqual("openai", bridge.btype["voice_to_text"])
            self.assertNotIn("voice_to_text", bridge.bots)

            with patch("bridge.bridge.create_voice", return_value=working_bot) as create:
                recovered_reply = bridge.fetch_voice_to_text("voice.wav")

            self.assertIs(expected_reply, recovered_reply)
            create.assert_called_once_with("openai", capability="voice_to_text")
            self.assertIs(working_bot, bridge.bots["voice_to_text"])

    def test_bridge_tts_recovers_after_custom_provider_is_fixed(self):
        from voice.custom.custom_voice import CustomVoice

        bridge = Bridge()
        with patch.dict(bridge.btype, {"text_to_voice": "custom:missing"}), \
                patch.dict(bridge.bots, {}, clear=True):
            reply = bridge.fetch_text_to_voice("hello")

            self.assertEqual(ReplyType.ERROR, reply.type)
            self.assertIsInstance(bridge.bots["text_to_voice"], CustomVoice)

            expected_reply = Reply(ReplyType.VOICE, "voice.mp3")
            working_bot = Mock()
            working_bot.textToVoice.return_value = expected_reply
            bridge.bots["text_to_voice"] = Mock(name="stale_text_to_voice_bot")

            corrected_config = {
                "voice_to_text": "openai",
                "text_to_voice": "openai",
                "use_linkai": False,
            }
            with patch("bridge.bridge.conf", return_value=corrected_config):
                bridge.refresh_voice()

            self.assertEqual("openai", bridge.btype["text_to_voice"])
            self.assertNotIn("text_to_voice", bridge.bots)

            with patch("bridge.bridge.create_voice", return_value=working_bot) as create:
                recovered_reply = bridge.fetch_text_to_voice("hello again")

            self.assertIs(expected_reply, recovered_reply)
            create.assert_called_once_with("openai", capability="text_to_voice")
            self.assertIs(working_bot, bridge.bots["text_to_voice"])

    def test_bridge_does_not_swallow_unexpected_asr_error(self):
        bridge = Bridge()
        broken_bot = Mock()
        broken_bot.voiceToText.side_effect = RuntimeError("unexpected ASR bug")
        with patch.dict(bridge.bots, {"voice_to_text": broken_bot}):
            with self.assertRaisesRegex(RuntimeError, "unexpected ASR bug"):
                bridge.fetch_voice_to_text("voice.wav")

    def test_bridge_does_not_swallow_unexpected_tts_error(self):
        bridge = Bridge()
        broken_bot = Mock()
        broken_bot.textToVoice.side_effect = RuntimeError("unexpected TTS bug")
        with patch.dict(bridge.bots, {"text_to_voice": broken_bot}):
            with self.assertRaisesRegex(RuntimeError, "unexpected TTS bug"):
                bridge.fetch_text_to_voice("hello")


if __name__ == "__main__":
    unittest.main()
