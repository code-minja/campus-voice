from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from campus_voice.services.tts_service import TTSService


class TestTTSModelFiles(unittest.TestCase):
    def test_downloads_missing_model_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_data = b"onnx-model"
            voices_data = b"voice-data"
            with patch.dict(
                "campus_voice.services.tts_service._KOKORO_MODEL_FILE_SIZES",
                {
                    "kokoro-v1.0.onnx": len(model_data),
                    "voices-v1.0.bin": len(voices_data),
                },
            ):
                responses = [io.BytesIO(model_data), io.BytesIO(voices_data)]
                with patch(
                    "campus_voice.services.tts_service.urllib.request.urlopen",
                    side_effect=responses,
                ) as urlopen:
                    model_path, voices_path = TTSService._ensure_model_files(
                        Path(directory)
                    )

            self.assertEqual(model_path.read_bytes(), model_data)
            self.assertEqual(voices_path.read_bytes(), voices_data)
            self.assertEqual(urlopen.call_count, 2)

    def test_reuses_existing_model_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "kokoro-v1.0.onnx"
            voices_path = Path(directory) / "voices-v1.0.bin"
            model_path.write_bytes(b"onnx-model")
            voices_path.write_bytes(b"voice-data")

            with patch.dict(
                "campus_voice.services.tts_service._KOKORO_MODEL_FILE_SIZES",
                {
                    "kokoro-v1.0.onnx": len(b"onnx-model"),
                    "voices-v1.0.bin": len(b"voice-data"),
                },
            ):
                with patch(
                    "campus_voice.services.tts_service.urllib.request.urlopen"
                ) as urlopen:
                    result = TTSService._ensure_model_files(Path(directory))

            self.assertEqual(result, (model_path, voices_path))
            urlopen.assert_not_called()

    def test_replaces_existing_file_with_wrong_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "kokoro-v1.0.onnx"
            voices_path = Path(directory) / "voices-v1.0.bin"
            model_path.write_bytes(b"truncated")
            voices_path.write_bytes(b"voice-data")

            with patch.dict(
                "campus_voice.services.tts_service._KOKORO_MODEL_FILE_SIZES",
                {
                    "kokoro-v1.0.onnx": len(b"complete-model"),
                    "voices-v1.0.bin": len(b"voice-data"),
                },
            ):
                with patch(
                    "campus_voice.services.tts_service.urllib.request.urlopen",
                    return_value=io.BytesIO(b"complete-model"),
                ) as urlopen:
                    TTSService._ensure_model_files(Path(directory))

            self.assertEqual(model_path.read_bytes(), b"complete-model")
            urlopen.assert_called_once()

    def test_rejects_truncated_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                "campus_voice.services.tts_service._KOKORO_MODEL_FILE_SIZES",
                {"kokoro-v1.0.onnx": 10, "voices-v1.0.bin": 10},
            ):
                with patch(
                    "campus_voice.services.tts_service.urllib.request.urlopen",
                    return_value=io.BytesIO(b"short"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "Expected 10 bytes"):
                        TTSService._ensure_model_files(Path(directory))

            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_failed_download_removes_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                "campus_voice.services.tts_service._KOKORO_MODEL_FILE_SIZES",
                {"kokoro-v1.0.onnx": 10, "voices-v1.0.bin": 10},
            ):
                with patch(
                    "campus_voice.services.tts_service.urllib.request.urlopen",
                    side_effect=OSError("network unavailable"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "network access"):
                        TTSService._ensure_model_files(Path(directory))

            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
