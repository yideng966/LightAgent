# encoding:utf-8
import os
import tempfile
import unittest
from unittest.mock import Mock, call, patch

from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.channel import Channel
from channel.chat_channel import ChatChannel


class TestChatChannelVoice(unittest.TestCase):
    def test_asr_text_uses_voice_transcription_hook(self):
        channel = object.__new__(ChatChannel)

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "voice.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"ID3test-audio")
            context = Context(
                ContextType.VOICE,
                audio_path,
                {"msg": Mock()},
            )
            channel._handle_voice_transcription = Mock(return_value=None)

            with patch("voice.audio_convert.any_to_wav"), patch.object(
                Channel,
                "build_voice_to_text",
                return_value=Reply(ReplyType.TEXT, "transcribed text"),
            ):
                reply = channel._generate_reply(context)

        self.assertIsNone(reply)
        channel._handle_voice_transcription.assert_called_once_with(
            context,
            "transcribed text",
        )

    def test_silk_conversion_failure_stops_before_asr(self):
        channel = object.__new__(ChatChannel)

        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, "voice.silk")
            with open(silk_path, "wb") as f:
                f.write(b"#!SILK_V3")
            context = Context(
                ContextType.VOICE,
                silk_path,
                {"msg": Mock()},
            )

            with patch(
                "voice.audio_convert.any_to_wav",
                side_effect=ImportError("pysilk-mod is required"),
            ), patch.object(
                Channel,
                "build_voice_to_text",
                return_value=Reply(ReplyType.ERROR, "downstream should not run"),
            ) as build_voice_to_text:
                reply = channel._generate_reply(context)

        build_voice_to_text.assert_not_called()
        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertIn("pysilk-mod", reply.content)

    def test_silk_decode_error_does_not_expose_exception_details(self):
        channel = object.__new__(ChatChannel)
        sensitive_path = r"C:\private\wechat\voice.silk"
        sensitive_data = "token=secret-value"

        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, "voice.silk")
            with open(silk_path, "wb") as f:
                f.write(b"#!SILK_V3")
            context = Context(
                ContextType.VOICE,
                silk_path,
                {"msg": Mock()},
            )

            with patch(
                "voice.audio_convert.any_to_wav",
                side_effect=RuntimeError(
                    f"decoder failed at {sensitive_path}; {sensitive_data}"
                ),
            ), patch.object(Channel, "build_voice_to_text") as build_voice_to_text:
                reply = channel._generate_reply(context)

        build_voice_to_text.assert_not_called()
        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertNotIn(sensitive_path, reply.content)
        self.assertNotIn(sensitive_data, reply.content)
        self.assertNotIn("decoder failed", reply.content)

    def test_mpeg_audio_with_silk_extension_falls_back_to_asr_alias(self):
        channel = object.__new__(ChatChannel)

        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, "voice.sil")
            with open(silk_path, "wb") as f:
                f.write(b"\xff\xf3\x38\xc4\x00\x0f\x98\x0a")
            context = Context(
                ContextType.VOICE,
                silk_path,
                {"msg": Mock()},
            )

            with patch(
                "voice.audio_convert.any_to_wav",
                side_effect=ImportError("pydub is required"),
            ), patch.object(
                Channel,
                "build_voice_to_text",
                return_value=Reply(ReplyType.ERROR, "asr reached"),
            ) as build_voice_to_text:
                reply = channel._generate_reply(context)
                asr_path = build_voice_to_text.call_args.args[0]
                self.assertTrue(asr_path.endswith(".mp3"))
                self.assertFalse(os.path.exists(asr_path))

        self.assertEqual("asr reached", reply.content)

    def test_asr_alias_does_not_overwrite_existing_audio_file(self):
        channel = object.__new__(ChatChannel)

        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, "voice.sil")
            existing_mp3_path = os.path.join(tmpdir, "voice.mp3")
            with open(silk_path, "wb") as f:
                f.write(b"\xff\xf3\x38\xc4\x00\x0f\x98\x0a")
            with open(existing_mp3_path, "wb") as f:
                f.write(b"existing-audio")
            context = Context(
                ContextType.VOICE,
                silk_path,
                {"msg": Mock()},
            )

            with patch(
                "voice.audio_convert.any_to_wav",
                side_effect=ImportError("pydub is required"),
            ), patch.object(
                Channel,
                "build_voice_to_text",
                return_value=Reply(ReplyType.ERROR, "asr reached"),
            ) as build_voice_to_text:
                channel._generate_reply(context)
                asr_path = build_voice_to_text.call_args.args[0]
                self.assertTrue(asr_path.endswith(".mp3"))
                self.assertNotEqual(existing_mp3_path, asr_path)

            with open(existing_mp3_path, "rb") as f:
                self.assertEqual(b"existing-audio", f.read())

    def test_wechat_group_voice_keeps_archived_source_file(self):
        channel = object.__new__(ChatChannel)

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "voice.mp3")
            wav_path = os.path.join(tmpdir, "voice.wav")
            with open(audio_path, "wb") as f:
                f.write(b"mp3-data")
            msg = Mock()
            msg.media_path = audio_path
            context = Context(
                ContextType.VOICE,
                audio_path,
                {
                    "msg": msg,
                    "channel_type": "wechat_group",
                },
            )

            with patch(
                "voice.audio_convert.any_to_wav",
                side_effect=RuntimeError("conversion failed"),
            ), patch.object(
                Channel,
                "build_voice_to_text",
                return_value=Reply(ReplyType.ERROR, "raw audio handled"),
            ) as build_voice_to_text:
                reply = channel._generate_reply(context)

            self.assertTrue(os.path.exists(audio_path))
            self.assertFalse(os.path.exists(wav_path))

        build_voice_to_text.assert_called_once_with(audio_path)
        self.assertEqual("raw audio handled", reply.content)

    def test_non_silk_fallback_cleans_partial_wav_after_first_cleanup_failure(self):
        channel = object.__new__(ChatChannel)

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "voice.mp3")
            wav_path = os.path.join(tmpdir, "voice.wav")
            with open(audio_path, "wb") as f:
                f.write(b"mp3-data")
            context = Context(
                ContextType.VOICE,
                audio_path,
                {"msg": Mock()},
            )

            def write_partial_wav_then_fail(_source, target):
                with open(target, "wb") as f:
                    f.write(b"partial-wav")
                raise RuntimeError("conversion failed")

            with patch(
                "voice.audio_convert.any_to_wav",
                side_effect=write_partial_wav_then_fail,
            ), patch.object(
                Channel,
                "build_voice_to_text",
                return_value=Reply(ReplyType.ERROR, "raw audio handled"),
            ) as build_voice_to_text, patch(
                "channel.chat_channel.os.remove",
                side_effect=[PermissionError("source is locked"), None],
            ) as remove:
                reply = channel._generate_reply(context)

        build_voice_to_text.assert_called_once_with(audio_path)
        self.assertEqual("raw audio handled", reply.content)
        self.assertEqual(
            [call(audio_path), call(wav_path)],
            remove.call_args_list,
        )


if __name__ == "__main__":
    unittest.main()
