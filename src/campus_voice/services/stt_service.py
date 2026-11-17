"""
Speech-to-Text service backed by faster-whisper 1.1.x + CTranslate2 4.5.x.

Dependency notes (as of May 2026)
-----------------------------------
* faster-whisper >= 1.1 requires `av` (PyAV).  PyAV bundles its own FFmpeg
  wheels — no system FFmpeg install, no build pain.
* ctranslate2 >= 4.5 supports NumPy 2.x (no more numpy<2 upper bound).
* faster-whisper.transcribe() accepts a BinaryIO / bytes-like object directly
  when av is present, so we no longer need a manual soundfile decode step.

Design principles
-----------------
* Model is loaded ONCE via load() and held in memory.
* transcribe() is synchronous (CPU-bound); call from a thread pool in routes.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from faster_whisper import WhisperModel

from campus_voice.core.config import Settings
from campus_voice.core.logging import get_logger

logger = get_logger(__name__)

# Curated, compact hotword list. faster-whisper prefills these on every call
# and silently truncates beyond max_length // 2 - 1 tokens, so keep only
# acronyms / hard-to-hear aliases and stay under ~600 characters.
_HOTWORDS = (
    "ETF", "E T F", "ETF 750",
    "30CQ", "thirty C Q",
    "TET 650", "TETFund 650",
    "OBJ", "O B J",
    "LT", "L T", "L T A",
    "RC", "R C",
    "AAUA", "A A U A",
)


@dataclass
class TranscriptionResult:
    text: str
    language: str
    language_probability: float
    segments: list[dict] = field(default_factory=list)


class STTService:
    """Wraps faster-whisper; safe to call from multiple threads after load()."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: WhisperModel | None = None
        self._hotwords: str | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def load(self) -> None:
        s = self._settings
        self._model = WhisperModel(
            model_size_or_path=s.whisper_model_size,
            device=s.whisper_device,
            compute_type=s.whisper_compute_type,
            download_root=str(s.whisper_download_root),
        )
        self._hotwords = ", ".join(_HOTWORDS) or None
        logger.info(
            "stt_service.loaded",
            model=s.whisper_model_size,
            device=s.whisper_device,
            compute_type=s.whisper_compute_type,
            language=s.whisper_language,
            beam_size=s.whisper_beam_size,
            hotword_chars=len(self._hotwords or ""),
        )

    def unload(self) -> None:
        self._model = None
        logger.info("stt_service.unloaded")

    # ── Public API ───────────────────────────────────────────────────────────

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        language: str | None = None,
        task: str = "transcribe",
    ) -> TranscriptionResult:
        """
        Transcribe raw audio bytes.

        faster-whisper uses PyAV internally to decode any format (wav, mp3,
        ogg, flac, m4a, webm) directly from a BytesIO buffer — no temp files,
        no external ffmpeg binary required.

        Parameters
        ----------
        audio_bytes : bytes
            Raw audio file content (any format av/FFmpeg can decode).
        language : str | None
            BCP-47 language code hint (e.g. "en", "yo").  None → settings.whisper_language ("en").
        task : str
            "transcribe" (default) or "translate" → English output.
        """
        if self._model is None:
            raise RuntimeError("STTService.load() has not been called")

        # Pass a BytesIO — faster-whisper 1.1.x accepts BinaryIO directly
        audio_buf = io.BytesIO(audio_bytes)
        segments_iter, info = self._model.transcribe(
            audio_buf,
            language=language or self._settings.whisper_language,
            task=task,
            beam_size=self._settings.whisper_beam_size,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            hotwords=self._hotwords if task == "transcribe" else None,
            condition_on_previous_text=False,
        )

        segments = []
        full_text_parts: list[str] = []
        for seg in segments_iter:
            segments.append(
                {
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                }
            )
            full_text_parts.append(seg.text)

        return TranscriptionResult(
            text=" ".join(full_text_parts).strip(),
            language=info.language,
            language_probability=round(info.language_probability, 4),
            segments=segments,
        )

