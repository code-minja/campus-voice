"""Tests for campus-specific STT post-processing."""

from __future__ import annotations

from campus_voice.services.text_processing.stt_postprocessor import STTPostProcessor


def test_corrects_spelled_out_acronym_destination() -> None:
    result = STTPostProcessor().process("take me to e t f 750")

    assert result.text == "take me to ETF 750"
    assert result.raw_text == "take me to e t f 750"
    assert result.post_processed is True
    assert result.corrections[0].replacement == "ETF 750"


def test_corrects_common_asr_variant_for_rc() -> None:
    result = STTPostProcessor().process("I am going to old are see")

    assert result.text == "I am going to Old RC"
    assert result.post_processed is True


def test_corrects_spoken_cq_variant_and_location_alias() -> None:
    result = STTPostProcessor().process("walk me to taxi Q")

    assert result.text == "walk me to 30CQ"
    assert result.post_processed is True


def test_normalizes_alias_from_location_data() -> None:
    result = STTPostProcessor().process("go to admin block")

    assert result.text == "go to Senate Building"
    assert result.post_processed is True


def test_removes_repeated_destination_from_transcription() -> None:
    result = STTPostProcessor().process(
        "I'm going to ETF 750, etf seven fifty,"
    )

    assert result.text == "I am going to ETF 750"
    assert result.post_processed is True


def test_leaves_unknown_text_unchanged() -> None:
    result = STTPostProcessor().process("hello from campus voice")

    assert result.text == "hello from campus voice"
    assert result.raw_text == "hello from campus voice"
    assert result.post_processed is False
    assert result.corrections == []
