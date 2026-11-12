# 🎙 Campus Voice — AI Voice Assistant Backend

A clean, production-ready FastAPI backend for the Campus Voice mobile app.

| Feature | Stack |
|---|---|
| **STT** | `faster-whisper` (CTranslate2, NumPy 1.x safe) |
| **TTS** | `kokoro` 82M ONNX model |
| **API** | FastAPI + uvicorn |
| **Deps** | `uv` |
| **Container** | Docker + Compose |
| **Python** | 3.11 |

---

## Project Structure

```
campus-voice/
├── src/campus_voice/
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py          # Router aggregator
│   │       └── routes/
│   │           ├── health.py        # GET  /v1/health
│   │           ├── stt.py           # POST /v1/stt/transcribe
│   │           └── tts.py           # POST /v1/tts/synthesize
│   ├── core/
│   │   ├── config.py                # Pydantic settings (env-driven)
│   │   ├── lifespan.py              # Model startup/shutdown (load ONCE)
│   │   └── logging.py              # structlog JSON logger
│   ├── models/
│   │   └── schemas.py               # Request / response Pydantic models
│   ├── services/
│   │   ├── stt_service.py           # faster-whisper wrapper
│   │   └── tts_service.py           # Kokoro TTS wrapper
│   ├── app.py                       # FastAPI factory
│   └── main.py                      # Entry point
├── tests/
│   └── test_api.py
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Quick Start

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone & set up

```bash
git clone <your-repo> campus-voice
cd campus-voice

cp .env.example .env
# Edit .env as needed

uv venv
uv pip install -e ".[dev]"
```

### 3. Run locally

```bash
uv run uvicorn campus_voice.main:app --reload --port 8000
```

Visit **http://localhost:8000/docs** for the interactive Swagger UI.
On the first local startup, the Kokoro ONNX model and voice files are downloaded
to `models/kokoro/` (about 354 MB total). Set `KOKORO_MODEL_PATH` to use another
directory. Docker continues to use the model files bundled at `/app`.

---

## API Endpoints

### `POST /v1/stt/transcribe`

Upload audio → receive transcribed text.

**Request** — multipart/form-data:
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | audio file | ✅ | wav, mp3, ogg, flac, m4a (max 25 MB) |
| `language` | string | ❌ | BCP-47 hint e.g. `en`, `yo`. Auto-detect if omitted |
| `task` | string | ❌ | `transcribe` (default) or `translate` → English |

Transcription is biased with the campus locations and their aliases, then
known destination aliases are normalized in the returned text.

**Response**:
```json
{
  "text": "Hello from Campus Voice",
  "language": "en",
  "language_probability": 0.99,
  "segments": [
    { "start": 0.0, "end": 1.2, "text": "Hello from Campus Voice" }
  ]
}
```

---

### `POST /v1/tts/synthesize`

Text → audio stream.

**Request** — JSON:
```json
{
  "text": "Hello, welcome to Campus Voice!",
  "voice": "af_heart",
  "speed": 1.0,
  "format": "wav"
}
```

**Response**: Raw audio bytes with `Content-Type: audio/wav` (or `audio/mpeg`).

**Available voices**: `af_heart`, `af_bella`, `am_adam`, `am_michael`, `bf_emma`, `bm_george`

---

### `GET /v1/health`

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": { "stt": "ready", "tts": "ready" }
}
```

---

## Docker

```bash
# Production
docker compose up campus-voice

# Dev (hot-reload, source mounted)
docker compose --profile dev up campus-voice-dev
```

Kokoro model files are bundled into the Docker image. Whisper models and Hugging
Face caches are persisted in named Docker volumes.

On macOS, the dev profile binds your local `src/` directory into the container.
If Docker Desktop shows a `Mounts denied` error, add the repo parent folder to
Docker Desktop's File Sharing list or move the project into a shared path such
as `/Users/<you>/...`. The production `campus-voice` service does not use a
source bind mount, so it can still run without that dev sharing setup.

### Route Preview Test

The `/v1/route` endpoint is geofenced to AAUA campus by default and supports
device GPS origins for real navigation. Simulated origins are disabled by
default; enable `ALLOW_SIMULATED_ORIGIN=true` in `.env` only when testing:

```bash
curl -X POST http://localhost:8000/v1/route \
  -H "Content-Type: application/json" \
  -d '{
    "simulate_origin": {
      "latitude": 7.481843099892803,
      "longitude": 5.741945337431659
    },
    "destination_name": "ETF750"
  }'
```

You can also route by numeric destination:

```json
{
  "origin": { "latitude": 7.4818, "longitude": 5.7420 },
  "destination_id": 1
}
```

---

## Configuration

All settings are environment variables (see `.env.example`):

| Variable | Default | Notes |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `base` | `tiny`→`large-v3` — bigger = more accurate |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | `int8` (CPU), `float16` (GPU) |
| `KOKORO_MODEL_PATH` | `models/kokoro/` | Directory for Kokoro model and voice files |
| `KOKORO_VOICE` | `af_heart` | See voice list above |
| `KOKORO_SPEED` | `1.0` | 0.5 – 2.0 |
| `TTS_OUTPUT_FORMAT` | `wav` | `wav` or `mp3` |
| `CORS_ORIGINS` | `["*"]` | Restrict in production |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` |
| `ROUTING_PROVIDER` | `google_routes` | Google Routes by default; `mock` is for explicit testing only |
| `GOOGLE_MAPS_API_KEY` | *(None)* | Required by Google Routes API |
| `ALLOW_SIMULATED_ORIGIN` | `false` | Rejects simulated origins unless explicitly enabled for testing |

AAUA routing is always restricted to the campus bounds and a 1,300 m radius
around the campus center. Geofence environment variables cannot disable or
expand that boundary.

---

## Tests

```bash
uv run pytest tests/ -v
```

---

## Expo React Native Integration

```typescript
// STT example
const formData = new FormData();
formData.append('file', {
  uri: audioUri,
  name: 'audio.wav',
  type: 'audio/wav',
} as any);

const response = await fetch('http://YOUR_SERVER:8000/v1/stt/transcribe', {
  method: 'POST',
  body: formData,
});
const { text } = await response.json();

// TTS example
const ttsResponse = await fetch('http://YOUR_SERVER:8000/v1/tts/synthesize', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: 'Hello!', format: 'wav' }),
});
const audioBlob = await ttsResponse.blob();
// play audioBlob with expo-av
```

---

## Roadmap

- [ ] Nigerian/Yoruba accent fine-tuning hooks
- [ ] Streaming TTS via Server-Sent Events
- [ ] Real-time WebSocket voice assistant session
- [ ] GPU support (CUDA Dockerfile variant)
- [ ] Auth middleware (JWT)

## STT Fine-Tuning

Recordings can be prepared with:

```bash
python scripts/prepare_stt_manifest.py
```

See [`docs/STT_FINE_TUNING.md`](docs/STT_FINE_TUNING.md) for the full workflow.

## Google Turn-by-Turn Routing

The backend can use Google Routes API for real walking directions and step-by-step
turn guidance.

Set:

```bash
ROUTING_PROVIDER=google_routes
GOOGLE_MAPS_API_KEY=your_google_api_key
```

Google's Routes API lets you request a route with HTTP POST and return the
distance, duration, and encoded polyline. The API also supports step-level
navigation instructions for turn-by-turn guidance. Google requires a Google
Cloud project with billing enabled for Maps Platform usage.

Google routing errors are returned instead of silently substituting mock routes.
