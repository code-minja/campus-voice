# ─────────────────────────────────────────────────────────────────────────────
# Campus Voice — Dockerfile
# Single-stage: install directly into system Python, no venv path confusion.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ src/

# Install directly into system Python — no venv, no path issues
RUN pip install --no-cache-dir --retries 5 --timeout 120 -e .

# Download Kokoro model files at build time so they're baked into the image.
# These are ~330MB total and live at a stable GitHub release URL.
RUN python -c "import pathlib, urllib.request; base='https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'; files=['kokoro-v1.0.onnx','voices-v1.0.bin']; p=pathlib.Path('/app'); [urllib.request.urlretrieve(base + name, p / name) for name in files]"

# Download Whisper base model at build time so it is baked into the image.
RUN python -c "from faster_whisper.utils import download_model; download_model('base', output_dir='/app/models/whisper')"


# Model cache dirs
ENV HF_HOME="/app/.cache/huggingface" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /app/.cache/huggingface /app/models/whisper

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health')"

CMD ["python", "-m", "uvicorn", "campus_voice.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
