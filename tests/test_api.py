"""
Minimal integration tests using FastAPI's TestClient.
Models are mocked so tests run without GPU or model downloads.
"""

from __future__ import annotations

import io
import wave
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from campus_voice.app import create_app
from campus_voice.data.campus_map import load_campus_map_points
from campus_voice.data.locations import LOCATIONS
from campus_voice.services.stt_service import TranscriptionResult
from campus_voice.services.tts_service import SynthesisResult


def _make_wav_bytes(duration_s: float = 0.5, sample_rate: int = 16_000) -> bytes:
    """Generate a minimal silent WAV file for testing."""
    import struct
    n_samples = int(duration_s * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"{n_samples}h", *([0] * n_samples)))
    return buf.getvalue()


@pytest.fixture()
def client():
    """TestClient with mocked ML services."""
    with patch("campus_voice.services.stt_service.STTService.load"), \
         patch("campus_voice.services.tts_service.TTSService.load"), \
         patch("campus_voice.services.stt_service.STTService.unload"), \
         patch("campus_voice.services.tts_service.TTSService.unload"):
        app = create_app()

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = TranscriptionResult(
            text="Hello from Campus Voice",
            language="en",
            language_probability=0.99,
            segments=[{"start": 0.0, "end": 1.0, "text": "Hello from Campus Voice"}],
        )

        wav_bytes = _make_wav_bytes()
        mock_tts = MagicMock()
        mock_tts.synthesize.return_value = SynthesisResult(
            audio_bytes=wav_bytes,
            sample_rate=24_000,
            format="wav",
            duration_seconds=0.5,
        )

        with TestClient(app) as c:
            c.app.state.stt = mock_stt
            c.app.state.tts = mock_tts
            yield c


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "stt" in body["services"]
    assert "tts" in body["services"]


def test_locations_expose_route_conditions(client: TestClient) -> None:
    r = client.get("/v1/locations")
    assert r.status_code == 200
    body = r.json()
    assert "locations" in body
    assert body["locations"]
    first_location = body["locations"][0]
    assert "route_conditions" in first_location
    assert isinstance(first_location["route_conditions"], list)
    assert {location["id"] for location in body["locations"]} == set(LOCATIONS)
    assert len(body["locations"]) == len(load_campus_map_points())
    assert {
        (location["latitude"], location["longitude"])
        for location in body["locations"]
    } == {
        (point.latitude, point.longitude)
        for point in load_campus_map_points()
    }
    assert "AAUA Main Gate" not in {location["name"] for location in body["locations"]}


# ── STT ───────────────────────────────────────────────────────────────────────

def test_transcribe_success(client: TestClient) -> None:
    wav = _make_wav_bytes()
    r = client.post(
        "/v1/stt/transcribe",
        files={"file": ("test.wav", wav, "audio/wav")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "Hello from Campus Voice"
    assert body["post_processed"] is False
    assert body["corrections"] == []
    assert body["language"] == "en"
    assert 0.0 <= body["language_probability"] <= 1.0


def test_transcribe_post_processes_campus_destination(client: TestClient) -> None:
    client.app.state.stt.transcribe.return_value = TranscriptionResult(
        text="take me to e t f 750",
        language="en",
        language_probability=0.99,
        segments=[{"start": 0.0, "end": 1.0, "text": "take me to e t f 750"}],
    )

    wav = _make_wav_bytes()
    r = client.post(
        "/v1/stt/transcribe",
        files={"file": ("test.wav", wav, "audio/wav")},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "take me to ETF 750"
    assert body["raw_text"] == "take me to e t f 750"
    assert body["post_processed"] is True
    assert body["corrections"][0]["replacement"] == "ETF 750"


def test_transcribe_matches_acoustic_variant_of_campus_destination(
    client: TestClient,
) -> None:
    client.app.state.stt.transcribe.return_value = TranscriptionResult(
        text="I am going to taxi Q",
        language="en",
        language_probability=0.99,
        segments=[{"start": 0.0, "end": 1.0, "text": "I am going to taxi Q"}],
    )

    r = client.post(
        "/v1/stt/transcribe",
        files={"file": ("test.wav", _make_wav_bytes(), "audio/wav")},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "I am going to 30CQ Lecture theater"
    assert body["raw_text"] == "I am going to taxi Q"
    assert body["post_processed"] is True


def test_transcribe_empty_file(client: TestClient) -> None:
    r = client.post(
        "/v1/stt/transcribe",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert r.status_code == 422


# ── TTS ───────────────────────────────────────────────────────────────────────

def test_synthesize_success(client: TestClient) -> None:
    r = client.post(
        "/v1/tts/synthesize",
        json={"text": "Hello Campus Voice!", "format": "wav"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert len(r.content) > 0


def test_synthesize_missing_text(client: TestClient) -> None:
    r = client.post("/v1/tts/synthesize", json={})
    assert r.status_code == 422


def test_synthesize_invalid_speed(client: TestClient) -> None:
    r = client.post(
        "/v1/tts/synthesize",
        json={"text": "test", "speed": 5.0},  # > 2.0 max
    )
    assert r.status_code == 422
