"""
Application configuration via environment variables.
All settings have sensible defaults for local dev.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "Campus Voice API"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # ── Server ───────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1  # keep 1 — models are not fork-safe

    # ── STT (faster-whisper) ─────────────────────────────────────────────────
    whisper_model_size: str = "base"  # tiny | base | small | medium | large-v3
    whisper_device: str = "cpu"       # cpu | cuda
    whisper_compute_type: str = "int8"  # int8 | float16 | float32
    whisper_language: str | None = "en"  # commands are English — skip auto-detect
    whisper_beam_size: int = 1          # greedy decoding; beam 5 is costly on CPU
    whisper_download_root: Path = Path("/app/models/whisper")

    # ── Campus geofence ─────────────────────────────────────────────────────
    # Legacy environment fields; route validation uses fixed AAUA boundary data.
    campus_geofence_enabled: bool = True
    campus_center_latitude: float = 7.479234
    campus_center_longitude: float = 5.748411
    campus_geofence_radius_meters: float = 1300.0
    allow_simulated_origin: bool = False

    # ── Routing provider ────────────────────────────────────────────────────
    routing_provider: str = "google_routes"  # mock | google_routes
    google_maps_api_key: str = ""
    google_routes_language_code: str = "en-US"
    google_routes_units: str = "METRIC"

    # ── TTS (Kokoro) ─────────────────────────────────────────────────────────
    kokoro_model_path: Path = (
        Path(__file__).resolve().parents[3] / "models" / "kokoro"
    )
    kokoro_voice: str = "af_heart"   # default voice
    kokoro_lang: str = "en-us"
    kokoro_speed: float = Field(default=1.0, ge=0.5, le=2.0)

    # ── Audio output ─────────────────────────────────────────────────────────
    tts_sample_rate: int = 24000
    tts_output_format: str = "wav"   # wav | mp3

    # ── CORS ────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
