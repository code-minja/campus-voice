"""
Text-to-Speech service backed by Kokoro 82M via kokoro-onnx.

Why kokoro-onnx instead of kokoro?
-----------------------------------
* No PyTorch dependency           → saves ~2 GB in Docker image
* No PyAV / FFmpeg build step     → no C++ compile pain
* No transformers / CUDA packages → lean CPU-only install (~300 MB total)
* Pure ONNX Runtime               → fast, portable, Python 3.11 stable

Design principles
-----------------
* Model is loaded ONCE via load() and held in memory.
* synthesize() is synchronous (CPU-bound); routes call it via thread pool.
* Audio is returned as raw bytes (WAV by default) — no temp files.
"""

from __future__ import annotations

import io
import tempfile
import threading
import time
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from campus_voice.core.config import Settings
from campus_voice.core.logging import get_logger

logger = get_logger(__name__)

_KOKORO_MODEL_BASE_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0"
)
_KOKORO_MODEL_FILE_SIZES = {
    "kokoro-v1.0.onnx": 325_532_387,
    "voices-v1.0.bin": 28_214_398,
}


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    sample_rate: int
    format: str           # "wav" | "mp3"
    duration_seconds: float


class TTSService:
    """Wraps kokoro-onnx; safe to call from multiple threads after load()."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._kokoro = None   # type: ignore[assignment]
        self._live = 0
        self._live_lock = threading.Lock()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Download missing model files and initialize the Kokoro ONNX model.

        For offline deployments, place both model files in KOKORO_MODEL_PATH
        before starting the application.
        """
        try:
            from kokoro_onnx import Kokoro  # type: ignore[import]
            import onnxruntime as ort

            model_path, voices_path = self._ensure_model_files(
                self._settings.kokoro_model_path
            )

            # Configure session options for minimal latency on CPU
            sess_opts = ort.SessionOptions()
            sess_opts.intra_op_num_threads = 2  # Prevent thread pool contention on standard CPU hosts
            sess_opts.inter_op_num_threads = 1
            sess_opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            providers = ["CPUExecutionProvider"]
            if "CUDAExecutionProvider" in ort.get_available_providers():
                providers.insert(0, "CUDAExecutionProvider")

            session = ort.InferenceSession(
                str(model_path), sess_opts, providers=providers
            )
            self._kokoro = Kokoro.from_session(session, str(voices_path))
            logger.info("tts_service.loaded_with_session", backend="kokoro-onnx", providers=providers)
        except Exception as exc:
            logger.error("tts_service.load_failed", error=str(exc))
            raise

    @staticmethod
    def _ensure_model_files(model_dir: Path) -> tuple[Path, Path]:
        model_dir.mkdir(parents=True, exist_ok=True)
        paths = (
            model_dir / "kokoro-v1.0.onnx",
            model_dir / "voices-v1.0.bin",
        )

        for path in paths:
            expected_size = _KOKORO_MODEL_FILE_SIZES[path.name]
            if path.is_file() and path.stat().st_size == expected_size:
                continue

            if path.exists():
                logger.warning(
                    "tts_service.model_file_size_mismatch",
                    file=path.name,
                    expected_bytes=expected_size,
                    actual_bytes=path.stat().st_size,
                )

            url = f"{_KOKORO_MODEL_BASE_URL}/{path.name}"
            logger.info(
                "tts_service.model_download_started",
                file=path.name,
                destination=str(path),
            )
            temporary_path: Path | None = None
            try:
                downloaded_bytes = 0
                next_progress_log = 32 * 1024 * 1024
                with tempfile.NamedTemporaryFile(
                    dir=model_dir,
                    prefix=f".{path.name}.",
                    suffix=".part",
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(temporary_file.name)
                    with urllib.request.urlopen(url, timeout=60) as response:
                        while chunk := response.read(1024 * 1024):
                            temporary_file.write(chunk)
                            downloaded_bytes += len(chunk)
                            if downloaded_bytes >= next_progress_log:
                                logger.info(
                                    "tts_service.model_download_progress",
                                    file=path.name,
                                    downloaded_bytes=downloaded_bytes,
                                    expected_bytes=expected_size,
                                )
                                next_progress_log = (
                                    downloaded_bytes // (32 * 1024 * 1024) + 1
                                ) * (32 * 1024 * 1024)

                if downloaded_bytes != expected_size:
                    raise OSError(
                        f"Expected {expected_size} bytes, received {downloaded_bytes}"
                    )
                temporary_path.replace(path)
                logger.info(
                    "tts_service.model_download_complete",
                    file=path.name,
                    size_bytes=path.stat().st_size,
                )
            except Exception as exc:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Could not download Kokoro model file {path.name} from {url}. "
                    f"Check network access or place the file in {model_dir}. {exc}"
                ) from exc

        return paths

    def unload(self) -> None:
        self._kokoro = None
        logger.info("tts_service.unloaded")

    # ── Public API ───────────────────────────────────────────────────────────

    def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float | None = None,
        output_format: str | None = None,
        background: bool = False,
    ) -> SynthesisResult:
        """
        Synthesize text to speech, yielding to live requests when prefetching.

        Live calls increment a counter; background prefetch work waits until
        it reaches zero so it never competes with a user's STT/TTS call.
        """
        if background:
            while self._live:
                time.sleep(0.05)
        else:
            with self._live_lock:
                self._live += 1
        try:
            return self._synthesize(
                text,
                voice=voice,
                speed=speed,
                output_format=output_format,
            )
        finally:
            if not background:
                with self._live_lock:
                    self._live -= 1

    def _synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float | None = None,
        output_format: str | None = None,
    ) -> SynthesisResult:
        """Synthesize text to speech audio bytes with disk caching."""
        import hashlib
        import json

        _voice = voice or self._settings.kokoro_voice
        _speed = speed or self._settings.kokoro_speed
        _fmt = (output_format or self._settings.tts_output_format).lower()

        # Simple thread-safe persistent disk cache
        cache_dir = self._settings.kokoro_model_path / "tts_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = hashlib.md5(f"{text}_{_voice}_{_speed}_{_fmt}".encode("utf-8")).hexdigest()
        cache_file = cache_dir / f"{cache_key}.{_fmt}"
        meta_file = cache_dir / f"{cache_key}.json"

        if cache_file.exists() and meta_file.exists():
            try:
                with open(meta_file, "r") as f:
                    meta = json.load(f)
                with open(cache_file, "rb") as f:
                    audio_bytes = f.read()
                logger.info(
                    "tts_service.cache_hit",
                    key=cache_key,
                    chars=len(text),
                    text=text[:30],
                )
                return SynthesisResult(
                    audio_bytes=audio_bytes,
                    sample_rate=meta["sample_rate"],
                    format=_fmt,
                    duration_seconds=meta["duration_seconds"],
                )
            except Exception as e:
                logger.warning("tts_service.cache_read_failed", error=str(e))

        if self._kokoro is None:
            raise RuntimeError("TTSService.load() has not been called")

        # kokoro-onnx API: create() → (samples: np.ndarray, sample_rate: int)
        audio_np, sample_rate = self._kokoro.create(
            text,
            voice=_voice,
            speed=_speed,
            lang=self._settings.kokoro_lang,
        )

        if audio_np is None or len(audio_np) == 0:
            raise ValueError("Kokoro returned empty audio for the given text")

        audio_np = audio_np.astype(np.float32)
        duration = len(audio_np) / sample_rate

        audio_bytes = self._encode(audio_np, sample_rate, _fmt)

        # Save to cache
        try:
            with open(meta_file, "w") as f:
                json.dump({
                    "sample_rate": sample_rate,
                    "duration_seconds": round(duration, 3)
                }, f)
            with open(cache_file, "wb") as f:
                f.write(audio_bytes)
            logger.info("tts_service.cached_new_synthesis", key=cache_key)
        except Exception as e:
            logger.warning("tts_service.cache_write_failed", error=str(e))

        logger.info(
            "tts_service.synthesized",
            chars=len(text),
            duration_s=round(duration, 2),
            voice=_voice,
            format=_fmt,
        )

        return SynthesisResult(
            audio_bytes=audio_bytes,
            sample_rate=sample_rate,
            format=_fmt,
            duration_seconds=round(duration, 3),
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _encode(audio: np.ndarray, sample_rate: int, fmt: str) -> bytes:
        """Encode float32 audio array to WAV or MP3 bytes."""
        audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)

        if fmt == "wav":
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)       # 16-bit PCM
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())
            return buf.getvalue()

        if fmt == "mp3":
            import soundfile as sf  # type: ignore[import]

            buf = io.BytesIO()
            sf.write(buf, audio, sample_rate, format="MP3")
            return buf.getvalue()

        raise ValueError(f"Unsupported format: {fmt!r}. Use 'wav' or 'mp3'.")
