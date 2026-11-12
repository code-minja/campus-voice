"""Tests for the faster-whisper service wrapper."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from campus_voice.core.config import Settings
from campus_voice.services.stt_service import STTService


def test_transcribe_uses_campus_hotwords_without_conflicting_prompt() -> None:
    with patch("campus_voice.services.stt_service.WhisperModel") as model_factory:
        model = model_factory.return_value
        model.transcribe.return_value = (
            iter([SimpleNamespace(start=0.0, end=0.5, text=" ETF 750")]),
            SimpleNamespace(language="en", language_probability=0.9),
        )
        service = STTService(Settings(_env_file=None))
        service.load()

        result = service.transcribe(b"audio")

    kwargs = model.transcribe.call_args.kwargs
    assert "ETF 750" in kwargs["hotwords"]
    assert "30CQ Lecture theater" in kwargs["hotwords"]
    assert kwargs["hotwords"].startswith("ETF 750, ETF, 30CQ")
    assert "initial_prompt" not in kwargs
    assert result.text == "ETF 750"
