# encoding:utf-8
import importlib.util
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from voice import audio_convert


class TestAudioConvert(unittest.TestCase):
    def test_silk_conversion_without_pysilk_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, "voice.silk")
            wav_path = os.path.join(tmpdir, "voice.wav")
            with open(silk_path, "wb") as f:
                f.write(b"#!SILK_V3")

            with patch.object(audio_convert, "pysilk", None, create=True):
                try:
                    audio_convert.any_to_wav(silk_path, wav_path)
                except ImportError as exc:
                    caught = exc
                except Exception as exc:
                    self.fail(f"missing pysilk raised {type(exc).__name__}: {exc}")
                else:
                    self.fail("missing pysilk did not raise ImportError")

        self.assertIn("pysilk-mod", str(caught))

    def test_silk_conversion_does_not_require_pydub(self):
        wav_data = b"RIFF\x00\x00\x00\x00WAVE"
        fake_pysilk = Mock()
        fake_pysilk.decode_file.return_value = wav_data

        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, "voice.slk")
            wav_path = os.path.join(tmpdir, "voice.wav")
            with open(silk_path, "wb") as f:
                f.write(b"#!SILK_V3")

            with patch.object(audio_convert, "pysilk", fake_pysilk, create=True), \
                    patch.object(audio_convert, "_pydub_available", False):
                try:
                    audio_convert.any_to_wav(silk_path, wav_path)
                except ImportError as exc:
                    self.fail(f"Silk conversion incorrectly required pydub: {exc}")

            with open(wav_path, "rb") as f:
                self.assertEqual(wav_data, f.read())

        fake_pysilk.decode_file.assert_called_once_with(
            silk_path,
            to_wav=True,
            sample_rate=24000,
        )

    def test_uppercase_silk_conversion_does_not_require_pydub(self):
        wav_data = b"RIFF\x00\x00\x00\x00WAVE"
        fake_pysilk = Mock()
        fake_pysilk.decode_file.return_value = wav_data

        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, "voice.SILK")
            wav_path = os.path.join(tmpdir, "voice.wav")
            with open(silk_path, "wb") as f:
                f.write(b"#!SILK_V3")

            with patch.object(audio_convert, "pysilk", fake_pysilk, create=True), \
                    patch.object(audio_convert, "_pydub_available", False):
                audio_convert.any_to_wav(silk_path, wav_path)

            with open(wav_path, "rb") as f:
                self.assertEqual(wav_data, f.read())

        fake_pysilk.decode_file.assert_called_once_with(
            silk_path,
            to_wav=True,
            sample_rate=24000,
        )

    def test_mpeg_audio_with_silk_extension_uses_pydub_not_pysilk(self):
        fake_pysilk = Mock()
        fake_audio = Mock()
        fake_audio.set_frame_rate.return_value = fake_audio
        fake_audio.set_channels.return_value = fake_audio

        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, "voice.sil")
            wav_path = os.path.join(tmpdir, "voice.wav")
            with open(silk_path, "wb") as f:
                f.write(b"\xff\xf3\x38\xc4\x00\x0f\x98\x0a")

            with patch.object(audio_convert, "pysilk", fake_pysilk, create=True), \
                    patch.object(audio_convert, "_pydub_available", True), \
                    patch.object(audio_convert, "AudioSegment") as audio_segment:
                audio_segment.from_file.return_value = fake_audio
                audio_convert.any_to_wav(silk_path, wav_path)

        fake_pysilk.decode_file.assert_not_called()
        audio_segment.from_file.assert_called_once_with(
            silk_path,
            parameters=["-nostdin"],
        )
        fake_audio.export.assert_called_once_with(
            wav_path,
            format="wav",
            codec="pcm_s16le",
        )

    @unittest.skipUnless(importlib.util.find_spec("pysilk"), "pysilk-mod is not installed")
    def test_pysilk_mod_round_trip_produces_wav(self):
        import pysilk

        sample_rate = 24000
        pcm_data = b"\x00\x00" * (sample_rate // 10)
        silk_data = pysilk.encode(pcm_data, data_rate=sample_rate, sample_rate=sample_rate)

        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, "voice.silk")
            wav_path = os.path.join(tmpdir, "voice.wav")
            with open(silk_path, "wb") as f:
                f.write(silk_data)

            audio_convert.any_to_wav(silk_path, wav_path)

            with open(wav_path, "rb") as f:
                wav_header = f.read(12)

        self.assertEqual(b"RIFF", wav_header[:4])
        self.assertEqual(b"WAVE", wav_header[8:12])


if __name__ == "__main__":
    unittest.main()
