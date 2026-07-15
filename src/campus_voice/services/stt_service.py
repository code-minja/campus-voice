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

import csv
import io
from pathlib import Path
from dataclasses import dataclass, field

from faster_whisper import WhisperModel

from campus_voice.core.config import Settings
from campus_voice.data.locations import LOCATIONS
from campus_voice.core.logging import get_logger

logger = get_logger(__name__)


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

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def load(self) -> None:
        s = self._settings
        self._model = WhisperModel(
            model_size_or_path=s.whisper_model_size,
            device=s.whisper_device,
            compute_type=s.whisper_compute_type,
            download_root=str(s.whisper_download_root),
        )
        logger.info(
            "stt_service.loaded",
            model=s.whisper_model_size,
            device=s.whisper_device,
            compute_type=s.whisper_compute_type,
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
            BCP-47 language code hint (e.g. "en", "yo").  None → auto-detect.
        task : str
            "transcribe" (default) or "translate" → English output.
        """
        if self._model is None:
            raise RuntimeError("STTService.load() has not been called")

        # Pass a BytesIO — faster-whisper 1.1.x accepts BinaryIO directly
        audio_buf = io.BytesIO(audio_bytes)
        initial_prompt = self._build_initial_prompt(task=task, language=language)

        segments_iter, info = self._model.transcribe(
            audio_buf,
            language=language,
            task=task,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=initial_prompt,
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

    def _build_initial_prompt(self, *, task: str, language: str | None) -> str | None:
        """
        Bias Whisper toward the campus vocabulary and command styles we expect.

        This is not true model fine-tuning, but with a small custom dataset it is
        the most practical accuracy boost we can apply during decoding.
        """
        if task != "transcribe":
            return None

        prompts: list[str] = [
            "Campus Voice navigation commands.",
            "Examples: take me to ETF 750, I am going to ETF 750, go to Senate Building, navigate to Old RC.",
        ]

        training_data_examples = self._load_training_transcripts()
        if training_data_examples:
            prompts.append(
                "Training examples: " + ", ".join(training_data_examples[:12])
            )

        destinations: list[str] = []
        for location in LOCATIONS.values():
            destinations.append(location["name"])
            destinations.extend(location["aliases"])

        # De-duplicate while preserving order so the prompt stays concise.
        unique_destinations = list(dict.fromkeys(destinations))
        if unique_destinations:
            prompts.append("Known campus destinations: " + ", ".join(unique_destinations))

        prompt = " ".join(prompts).strip()
        return prompt or None

    @staticmethod
    def _load_training_transcripts() -> list[str]:
        metadata_path = Path(__file__).resolve().parents[3] / "stt-training-data" / "metadata.csv"
        if not metadata_path.exists():
            return []

        transcripts: list[str] = []
        try:
            with metadata_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    transcript = (row.get("transcript") or "").strip()
                    if transcript:
                        transcripts.append(transcript)
        except Exception:
            return []

        return list(dict.fromkeys(transcripts))
