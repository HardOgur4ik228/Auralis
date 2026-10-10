# -*- coding: utf-8 -*-
"""
Auralis — transcription engine.

This module is the backend "brain": it knows nothing about HTTP. It deals with
ffmpeg, faster-whisper, background jobs, progress reporting and export formats.

The web layer (``app.py``) only orchestrates and serialises the data produced
here.  Progress/state is reported with machine-readable *stage* codes so the
frontend can localise messages, while technical error details are kept separate.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
import wave
from pathlib import Path

logger = logging.getLogger("auralis.engine")

# --------------------------------------------------------------------------- #
#  Capabilities / constants
# --------------------------------------------------------------------------- #

AUDIO_EXT = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma",
    ".aiff", ".aif", ".amr", ".mp2", ".oga", ".weba",
}
VIDEO_EXT = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v",
    ".mpg", ".mpeg", ".3gp", ".ts", ".ogv",
}
ALLOWED_EXT = AUDIO_EXT | VIDEO_EXT

MODELS = ["tiny", "base", "small", "medium", "large-v3"]

DEFAULT_MODEL = os.environ.get("AURALIS_MODEL", "small")
if DEFAULT_MODEL not in MODELS:
    DEFAULT_MODEL = "small"

LANGUAGES = [
    ("auto", "Auto-detect", "Автоопределение"),
    ("ru", "Russian", "Русский"),
    ("en", "English", "Английский"),
    ("uk", "Ukrainian", "Украинский"),
    ("de", "German", "Немецкий"),
    ("fr", "French", "Французский"),
    ("es", "Spanish", "Испанский"),
    ("it", "Italian", "Итальянский"),
    ("pt", "Portuguese", "Португальский"),
    ("pl", "Polish", "Польский"),
    ("tr", "Turkish", "Турецкий"),
    ("nl", "Dutch", "Нидерландский"),
    ("cs", "Czech", "Чешский"),
    ("sv", "Swedish", "Шведский"),
    ("ar", "Arabic", "Арабский"),
    ("hi", "Hindi", "Хинди"),
    ("zh", "Chinese", "Китайский"),
    ("ja", "Japanese", "Японский"),
    ("ko", "Korean", "Корейский"),
]
LANGUAGE_CODES = {code for code, _, _ in LANGUAGES}

TASKS = ("transcribe", "translate")
EXPORT_FORMATS = ("txt", "srt", "vtt", "json")

MAX_UPLOAD_BYTES = int(os.environ.get("AURALIS_MAX_UPLOAD", str(1024 ** 3)))
MAX_CONCURRENT_JOBS = max(1, int(os.environ.get("AURALIS_MAX_JOBS", "2")))
JOB_TTL_SECONDS = int(os.environ.get("AURALIS_JOB_TTL", "3600"))

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

# Stage codes shared with the frontend (localised there).
STAGES = ("queued", "extracting", "loading", "transcribing", "done")


class TranscriptionError(RuntimeError):
    """A user-facing error carrying a machine-readable code and a detail."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


class Canceled(Exception):
    """Raised internally when a job is canceled by the user."""


# --------------------------------------------------------------------------- #
#  ffmpeg helpers
# --------------------------------------------------------------------------- #

def _run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, check=False,
    )


def probe_duration(path: Path) -> float:
    """Return media duration in seconds (0.0 when unknown)."""
    if not FFPROBE:
        return 0.0
    try:
        res = _run([
            FFPROBE, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ], timeout=60)
        out = res.stdout.decode("utf-8", "ignore").strip()
        return float(out) if out else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def extract_audio(src: Path, dst: Path) -> None:
    """Extract/normalise the audio track to 16 kHz mono PCM WAV."""
    if not FFMPEG:
        raise TranscriptionError(
            "ffmpeg_missing",
            "ffmpeg was not found on PATH. Install it and restart the server.",
        )
    res = _run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dst),
    ], timeout=3600)
    if res.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        lines = res.stderr.decode("utf-8", "ignore").strip().splitlines()
        detail = lines[-1] if lines else "ffmpeg failed with no diagnostics"
        raise TranscriptionError("extract_failed", detail)


def load_audio_array(path: Path):
    """Read the 16 kHz mono WAV into a float32 numpy array.

    We decode ourselves with the stdlib ``wave`` module so the app does not
    depend on the PyAV version bundled with faster-whisper.
    """
    import numpy as np  # local import keeps module import cheap

    with wave.open(str(path), "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())

    if width != 2:
        raise TranscriptionError(
            "audio_decode_failed", f"unexpected WAV sample width: {width * 8} bit"
        )
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        raise TranscriptionError(
            "audio_decode_failed", f"unexpected sample rate: {rate} Hz"
        )
    return audio


# --------------------------------------------------------------------------- #
#  Model engine
# --------------------------------------------------------------------------- #

def resolve_device() -> tuple[str, str]:
    device = os.environ.get("AURALIS_DEVICE", "cpu").strip().lower()
    if device == "auto":
        try:
            import ctranslate2  # noqa: WPS433

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda", "float16"
        except Exception:  # noqa: BLE001
            pass
        return "cpu", "int8"
    if device == "cuda":
        return "cuda", "float16"
    return "cpu", "int8"


class Engine:
    """Thread-safe cache of loaded Whisper models and batched pipelines."""

    def __init__(self) -> None:
        self.device, self.compute_type = resolve_device()
        self._models: dict[str, object] = {}
        self._pipelines: dict[str, object] = {}
        # Re-entrant: pipeline() calls model() while holding the lock.
        self._lock = threading.RLock()

    def model(self, size: str):
        if size not in MODELS:
            size = DEFAULT_MODEL
        with self._lock:
            model = self._models.get(size)
            if model is None:
                from faster_whisper import WhisperModel  # noqa: WPS433

                logger.info(
                    "Loading Whisper model '%s' on %s (%s)",
                    size, self.device, self.compute_type,
                )
                model = WhisperModel(
                    size, device=self.device, compute_type=self.compute_type
                )
                self._models[size] = model
            return model

    def pipeline(self, size: str):
        """A :class:`BatchedInferencePipeline` sharing the cached model."""
        if size not in MODELS:
            size = DEFAULT_MODEL
        with self._lock:
            pipe = self._pipelines.get(size)
            if pipe is None:
                from faster_whisper import BatchedInferencePipeline  # noqa: WPS433

                logger.info("Creating batched pipeline for '%s'", size)
                pipe = BatchedInferencePipeline(model=self.model(size))
                self._pipelines[size] = pipe
            return pipe


# --------------------------------------------------------------------------- #
#  Job
# --------------------------------------------------------------------------- #

class Job:
    """Mutable state of a single transcription task."""

    def __init__(self, filename: str, options: dict) -> None:
        self.id = uuid.uuid4().hex
        self.filename = filename
        self.options = options
        self.created = time.time()
        self.finished = None

        self.status = "queued"          # queued|extracting|loading|transcribing|done|error|canceled
        self.progress = 0.0
        self.message_code = "queued"
        self.duration = 0.0
        self.detected_language = None
        self.language_probability = None

        self.text = ""
        self.segments: list[dict] = []
        self.stats: dict = {}
        self.has_speech = False

        self.error_code = None
        self.error_detail = None

        self.cancel_event = threading.Event()
        self.lock = threading.Lock()

    # -- state helpers ----------------------------------------------------- #

    def update(self, **fields) -> None:
        with self.lock:
            for key, value in fields.items():
                setattr(self, key, value)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "id": self.id,
                "filename": self.filename,
                "status": self.status,
                "progress": round(self.progress, 1),
                "message_code": self.message_code,
                "duration": round(self.duration, 2),
                "detected_language": self.detected_language,
                "language_probability": self.language_probability,
                "error_code": self.error_code,
                "error_detail": self.error_detail,
                "cancelable": self.status in ("queued", "extracting", "loading", "transcribing"),
            }

    def public_result(self) -> dict:
        with self.lock:
            return {
                "id": self.id,
                "filename": self.filename,
                "status": self.status,
                "options": self.options,
                "text": self.text,
                "segments": self.segments,
                "stats": self.stats,
                "has_speech": self.has_speech,
                "duration": round(self.duration, 2),
                "detected_language": self.detected_language,
                "language_probability": self.language_probability,
                "error_code": self.error_code,
                "error_detail": self.error_detail,
            }


# --------------------------------------------------------------------------- #
#  Manager
# --------------------------------------------------------------------------- #

class Manager:
    """Owns the job table, the worker semaphore and temporary files."""

    def __init__(self, work_dir: Path) -> None:
        self.work_dir = work_dir
        self.uploads_dir = work_dir / "uploads"
        self.audio_dir = work_dir / "audio"
        for d in (self.uploads_dir, self.audio_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.engine = Engine()
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(MAX_CONCURRENT_JOBS)

        threading.Thread(target=self._cleanup_loop, daemon=True,
                         name="auralis-cleanup").start()

    # -- public API -------------------------------------------------------- #

    def save_upload(self, job: Job, file_storage) -> Path:
        ext = Path(job.filename).suffix.lower()
        path = self.uploads_dir / f"{job.id}{ext}"
        file_storage.save(str(path))
        if not path.exists() or path.stat().st_size == 0:
            path.unlink(missing_ok=True)
            raise TranscriptionError("empty_file", "The uploaded file is empty.")
        return path

    def create(self, filename: str, options: dict) -> Job:
        job = Job(filename, options)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def submit(self, job: Job, upload_path: Path) -> None:
        threading.Thread(
            target=self._run, args=(job, upload_path),
            daemon=True, name=f"auralis-job-{job.id[:8]}",
        ).start()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        job.cancel_event.set()
        return True

    def remove(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        job.cancel_event.set()
        with self._lock:
            self._jobs.pop(job_id, None)
        self._remove_files(job_id)
        return True

    def counts(self) -> dict:
        with self._lock:
            jobs = list(self._jobs.values())
        active = sum(1 for j in jobs if j.status in
                     ("queued", "extracting", "loading", "transcribing"))
        return {"total": len(jobs), "active": active,
                "capacity": MAX_CONCURRENT_JOBS}

    # -- internals --------------------------------------------------------- #

    def _run(self, job: Job, upload_path: Path) -> None:
        audio_path = self.audio_dir / f"{job.id}.wav"
        acquired = False
        try:
            # Wait for a free worker slot (keeps memory bounded).
            while not self._slots.acquire(timeout=0.5):
                if job.cancel_event.is_set():
                    raise Canceled()

            acquired = True
            if job.cancel_event.is_set():
                raise Canceled()
            self._process(job, upload_path, audio_path)

        except Canceled:
            job.update(status="canceled", message_code="canceled",
                       error_code=None, error_detail=None)
        except TranscriptionError as exc:
            job.update(status="error", message_code="error",
                       error_code=exc.code, error_detail=exc.detail)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error in job %s", job.id)
            job.update(status="error", message_code="error",
                       error_code="unknown", error_detail=str(exc))
        finally:
            if acquired:
                self._slots.release()
            job.finished = time.time()
            self._remove_files(job.id)

    def _process(self, job: Job, upload_path: Path, audio_path: Path) -> None:
        started = time.time()

        # 1) Extract audio -------------------------------------------------- #
        job.update(status="extracting", message_code="extracting", progress=3)
        extract_audio(upload_path, audio_path)
        if job.cancel_event.is_set():
            raise Canceled()
        source_duration = probe_duration(audio_path)
        job.update(duration=source_duration)
        if source_duration <= 0:
            source_duration = probe_duration(upload_path) or 0.0
        job.update(progress=8)

        # 2) Load model ----------------------------------------------------- #
        job.update(status="loading", message_code="loading", progress=12)
        size = job.options["model"]
        try:
            if job.options["batch_size"] and job.options["batch_size"] > 0:
                runner = self.engine.pipeline(size)
                batched = True
            else:
                runner = self.engine.model(size)
                batched = False
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionError("model_failed", str(exc)) from exc

        if job.cancel_event.is_set():
            raise Canceled()

        # 3) Transcribe ----------------------------------------------------- #
        job.update(status="transcribing", message_code="transcribing", progress=15)
        audio = load_audio_array(audio_path)

        language = None if job.options["language"] == "auto" else job.options["language"]
        kwargs = dict(
            language=language,
            task=job.options["task"],
            beam_size=5,
            vad_filter=job.options["vad"],
            word_timestamps=job.options["word_timestamps"],
            without_timestamps=False,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        if batched:
            kwargs["batch_size"] = int(job.options["batch_size"])
            kwargs["condition_on_previous_text"] = False

        try:
            segments_iter, info = runner.transcribe(audio, **kwargs)
        except TypeError:
            # Very defensive: drop batched-only / unsupported kwargs and retry.
            for key in ("batch_size", "condition_on_previous_text", "without_timestamps"):
                kwargs.pop(key, None)
            segments_iter, info = runner.transcribe(audio, **kwargs)

        total = float(getattr(info, "duration", 0.0) or source_duration or 0.0)
        job.update(
            duration=total or source_duration,
            detected_language=getattr(info, "language", None),
            language_probability=round(
                float(getattr(info, "language_probability", 0.0) or 0.0), 3),
        )

        collected: list[dict] = []
        last_push = 0.0
        for seg in segments_iter:
            if job.cancel_event.is_set():
                raise Canceled()
            text = (seg.text or "").strip()
            if text:
                item = {
                    "start": round(float(seg.start), 2),
                    "end": round(float(seg.end), 2),
                    "text": text,
                }
                words = getattr(seg, "words", None)
                if words and job.options["word_timestamps"]:
                    item["words"] = [
                        {"start": round(float(w.start), 2),
                         "end": round(float(w.end), 2),
                         "text": (w.word or "").strip()}
                        for w in words
                    ]
                collected.append(item)

            baseline = 15.0
            if total > 0:
                pct = baseline + min(float(seg.end) / total, 1.0) * (98 - baseline)
            else:
                pct = min(98.0, job.progress + 1)
            now = time.time()
            if now - last_push > 0.25:
                job.update(progress=min(pct, 98))
                last_push = now

        text = "\n".join(s["text"] for s in collected).strip()
        elapsed = max(time.time() - started, 1e-6)
        stats = {
            "segments": len(collected),
            "characters": len(text),
            "words": len(text.split()),
            "duration": round(total or source_duration, 2),
            "elapsed": round(elapsed, 2),
            "speed": round((total or source_duration) / elapsed, 2) if total else 0,
        }

        job.update(
            status="done", message_code="done", progress=100,
            text=text, segments=collected, stats=stats,
            has_speech=bool(collected),
        )

    def _remove_files(self, job_id: str) -> None:
        for directory in (self.uploads_dir, self.audio_dir):
            for path in directory.glob(f"{job_id}.*"):
                try:
                    path.unlink()
                except OSError:
                    pass

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(60)
            cutoff = time.time() - JOB_TTL_SECONDS
            stale: list[str] = []
            with self._lock:
                for jid, job in self._jobs.items():
                    if job.finished and job.finished < cutoff:
                        stale.append(jid)
                for jid in stale:
                    self._jobs.pop(jid, None)
            for jid in stale:
                self._remove_files(jid)
                logger.info("Cleaned up stale job %s", jid)


# --------------------------------------------------------------------------- #
#  Export formatters
# --------------------------------------------------------------------------- #

def _hms(seconds: float, millis_sep: str = ",") -> str:
    if seconds < 0:
        seconds = 0
    millis = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{millis_sep}{millis:03d}"


def format_txt(job: Job) -> str:
    return (job.text or "") + "\n"


def format_srt(job: Job) -> str:
    blocks = []
    for i, seg in enumerate(job.segments, 1):
        blocks.append(str(i))
        blocks.append(f"{_hms(seg['start'])} --> {_hms(seg['end'])}")
        blocks.append(seg["text"])
        blocks.append("")
    return "\n".join(blocks).strip() + ("\n" if blocks else "")


def format_vtt(job: Job) -> str:
    lines = ["WEBVTT", ""]
    for seg in job.segments:
        lines.append(f"{_hms(seg['start'], '.')} --> {_hms(seg['end'], '.')}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def format_json(job: Job) -> str:
    payload = {
        "id": job.id,
        "filename": job.filename,
        "language": job.detected_language,
        "language_probability": job.language_probability,
        "duration": job.duration,
        "text": job.text,
        "stats": job.stats,
        "segments": job.segments,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


FORMATTERS = {
    "txt": (format_txt, "text/plain; charset=utf-8", ".txt"),
    "srt": (format_srt, "application/x-subrip; charset=utf-8", ".srt"),
    "vtt": (format_vtt, "text/vtt; charset=utf-8", ".vtt"),
    "json": (format_json, "application/json; charset=utf-8", ".json"),
}
