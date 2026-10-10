# Auralis API — container for Python hosts such as Render, Fly.io, HF Spaces.
# Cloudflare Pages (static frontend) does NOT execute Python —
# the Flask API lives in this container, the UI lives in public/ on Pages.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AURALIS_HOST=0.0.0.0 \
    AURALIS_MODEL=base \
    AURALIS_DEVICE=cpu \
    AURALIS_MAX_JOBS=1

# faster-whisper needs ffmpeg to extract the audio track from files.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Single worker, several threads: the app spawns its own per-job threads.
CMD ["gunicorn", "app:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "900", \
     "--graceful-timeout", "30"]