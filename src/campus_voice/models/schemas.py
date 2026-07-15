"""
Shared Pydantic models for API request/response schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


# ── STT ──────────────────────────────────────────────────────────────────────

class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionCorrection(BaseModel):
    kind: str
    original: str
    replacement: str
    confidence: float = Field(ge=0.0, le=1.0)


class TranscribeResponse(BaseModel):
    text: str = Field(description="Full transcribed text")
    raw_text: str | None = Field(
        default=None,
        description="Original text before post-processing, when different.",
    )
    post_processed: bool = Field(
        default=False,
        description="Whether server-side STT post-processing changed the text.",
    )
    corrections: list[TranscriptionCorrection] = Field(default_factory=list)
    language: str = Field(description="Detected language code (BCP-47)")
    language_probability: float = Field(ge=0.0, le=1.0)
    segments: list[TranscriptionSegment] = Field(default_factory=list)


# ── TTS ──────────────────────────────────────────────────────────────────────

class SynthesizeRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=5000,
        description="Text to synthesize",
        examples=["Hello, welcome to Campus Voice!"],
    )
    voice: str | None = Field(
        default=None,
        description="Kokoro voice ID (e.g. 'af_heart', 'am_adam'). "
                    "Omit to use server default.",
    )
    speed: float | None = Field(
        default=None,
        ge=0.5,
        le=2.0,
        description="Speech speed multiplier (0.5–2.0)",
    )
    format: str | None = Field(
        default=None,
        pattern="^(wav|mp3)$",
        description="Output audio format: 'wav' or 'mp3'",
    )


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict[str, str]


# ── Navigation ───────────────────────────────────────────────────────────────

class Coordinate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class RouteRequest(BaseModel):
    origin: Coordinate | None = Field(
        default=None,
        description="Device GPS coordinate. Required unless simulate_origin is supplied.",
    )
    simulate_origin: Coordinate | None = Field(
        default=None,
        description="Testing-only origin override for route simulation.",
    )
    destination_id: int | None = Field(default=None, ge=1)
    destination_name: str | None = Field(
        default=None,
        min_length=1,
        description="Destination name or alias, e.g. ETF750 or old rc.",
    )

    @model_validator(mode="after")
    def validate_route_request(self) -> "RouteRequest":
        if self.origin is None and self.simulate_origin is None:
            raise ValueError("origin or simulate_origin is required")
        if self.destination_id is None and self.destination_name is None:
            raise ValueError("destination_id or destination_name is required")
        return self


class DestinationSummary(BaseModel):
    id: int
    name: str
    coordinate: Coordinate | None = None


class GeofenceStatus(BaseModel):
    enabled: bool
    inside: bool
    center: Coordinate
    radius_meters: float
    distance_from_center_meters: float


class RouteStep(BaseModel):
    step_number: int | None = None
    instruction: str
    distance_meters: float = Field(..., ge=0)
    heading_degrees: float | None = Field(default=None, ge=0.0, lt=360.0)
    waypoint: Coordinate


class RouteResponse(BaseModel):
    origin: Coordinate
    destination: DestinationSummary
    geofence: GeofenceStatus
    route_preview: list[Coordinate]
    steps: list[RouteStep]
    total_distance_meters: float = Field(..., ge=0)
    estimated_duration_seconds: int = Field(..., ge=0)
    simulated: bool = False


class CampusRouteCondition(BaseModel):
    code: str
    label: str
    description: str
    severity: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)


class CampusLocation(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    aliases: list[str] = Field(default_factory=list)
    route_conditions: list[CampusRouteCondition] = Field(default_factory=list)


class CampusLocationsResponse(BaseModel):
    locations: list[CampusLocation]
