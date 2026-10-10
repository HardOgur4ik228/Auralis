# -*- coding: utf-8 -*-
"""
Auralis — Flask web layer.

Only HTTP concerns live here: routing, validation, JSON/SSE serialisation and
file downloads.  All transcription logic is delegated to ``transcription.py``.

Run:  python app.py
"""

from __future__ import annotations

import io
import json
import logging
import os
import time
from pathlib import Path

from flask import (
    Flask, Response, jsonify, render_template, request, send_file,
)

import transcription as engine_mod


# --------------------------------------------------------------------------- #
#  Logging
# --------------------------------------------------------------------------- #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("auralis.web")

BASE_DIR = Path(__file__).resolve().parent
WORK_DIR = Path(os.environ.get("AURALIS_WORK", BASE_DIR / "auralis_work"))
HOST = os.environ.get("AURALIS_HOST", "127.0.0.1")
PORT = int(os.environ.get("AURALIS_PORT", "5000"))
DEBUG = os.environ.get("AURALIS_DEBUG", "0") == "1"

manager = engine_mod.Manager(WORK_DIR)


# --------------------------------------------------------------------------- #
#  App
# --------------------------------------------------------------------------- #

def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["MAX_CONTENT_LENGTH"] = engine_mod.MAX_UPLOAD_BYTES
    app.config["JSON_AS_ASCII"] = False

    # ---- error handlers -------------------------------------------------- #

    @app.errorhandler(413)
    def _too_large(_):
        return _api_error("too_large", 413,
                          f"File is larger than {engine_mod.MAX_UPLOAD_BYTES} bytes.")

    @app.errorhandler(404)
    def _not_found(err):
        if request.path.startswith("/api/"):
            return _api_error("not_found", 404, "Resource not found.")
        return render_template("index.html"), 200

    @app.errorhandler(500)
    def _server_error(err):
        logger.exception("Server error")
        return _api_error("server_error", 500, "Internal server error.")

    # ---- pages ----------------------------------------------------------- #

    @app.get("/")
    def index():
        return render_template("index.html")

    # ---- API ------------------------------------------------------------- #

    @app.get("/api/health")
    def health():
        return jsonify({
            "ok": True,
            "ffmpeg": bool(engine_mod.FFMPEG),
            "ffprobe": bool(engine_mod.FFPROBE),
            "device": manager.engine.device,
            "compute_type": manager.engine.compute_type,
            "models": engine_mod.MODELS,
            "default_model": engine_mod.DEFAULT_MODEL,
            "tasks": list(engine_mod.TASKS),
            "languages": [
                {"code": c, "en": en, "ru": ru}
                for c, en, ru in engine_mod.LANGUAGES
            ],
            "formats": list(engine_mod.EXPORT_FORMATS),
            "max_upload": engine_mod.MAX_UPLOAD_BYTES,
            "audio_ext": sorted(engine_mod.AUDIO_EXT),
            "video_ext": sorted(engine_mod.VIDEO_EXT),
            "queue": manager.counts(),
        })

    @app.post("/api/jobs")
    def create_job():
        if not engine_mod.FFMPEG:
            return _api_error(
                "ffmpeg_missing", 503,
                "ffmpeg was not found on PATH. Install it and restart the server.",
            )

        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return _api_error("no_file", 400, "No file was uploaded.")

        filename = Path(upload.filename).name
        ext = Path(filename).suffix.lower()
        if ext not in engine_mod.ALLOWED_EXT:
            return _api_error(
                "invalid_format", 400,
                f"Unsupported format: {ext or '(no extension)'}.",
            )

        options = _parse_options(request.form)
        job = manager.create(filename, options)

        try:
            upload_path = manager.save_upload(job, upload)
        except engine_mod.TranscriptionError as exc:
            manager.remove(job.id)
            return _api_error(exc.code, 400, exc.detail)

        manager.submit(job, upload_path)
        logger.info("Job %s created: %s (%s)", job.id, filename, options)
        return jsonify({"id": job.id, "filename": filename, "options": options}), 202

    @app.get("/api/jobs/<job_id>")
    def job_result(job_id: str):
        job = manager.get(job_id)
        if job is None:
            return _api_error("job_not_found", 404, "Job not found.")
        return jsonify(job.public_result())

    @app.get("/api/jobs/<job_id>/stream")
    def job_stream(job_id: str):
        if manager.get(job_id) is None:
            return _api_error("job_not_found", 404, "Job not found.")

        def gen():
            last = None
            while True:
                job = manager.get(job_id)
                if job is None:
                    yield _sse({"status": "removed"})
                    break
                payload = json.dumps(job.snapshot(), ensure_ascii=False)
                if payload != last:
                    yield f"data: {payload}\n\n"
                    last = payload
                if job.status in ("done", "error", "canceled"):
                    break
                time.sleep(0.35)

        return Response(gen(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        })

    @app.get("/api/jobs/<job_id>/download")
    def job_download(job_id: str):
        job = manager.get(job_id)
        if job is None:
            return _api_error("job_not_found", 404, "Job not found.")
        if job.status != "done":
            return _api_error("not_ready", 409, "Result is not ready yet.")

        fmt = request.args.get("format", "txt").lower()
        if fmt not in engine_mod.FORMATTERS:
            return _api_error("bad_format", 400, f"Unknown export format: {fmt}.")

        formatter, mimetype, ext = engine_mod.FORMATTERS[fmt]
        data = formatter(job).encode("utf-8")
        stem = Path(job.filename).stem or "transcript"
        buf = io.BytesIO(data)
        return send_file(buf, mimetype=mimetype, as_attachment=True,
                         download_name=f"{stem}{ext}")

    @app.delete("/api/jobs/<job_id>")
    def job_delete(job_id: str):
        job = manager.get(job_id)
        if job is None:
            return _api_error("job_not_found", 404, "Job not found.")
        manager.remove(job_id)
        return jsonify({"ok": True, "id": job_id})

    return app


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _api_error(code: str, status: int, detail: str = ""):
    return jsonify({"error": code, "detail": detail}), status


def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _parse_options(form) -> dict:
    language = form.get("language", "auto")
    if language not in engine_mod.LANGUAGE_CODES:
        language = "auto"

    model = form.get("model", engine_mod.DEFAULT_MODEL)
    if model not in engine_mod.MODELS:
        model = engine_mod.DEFAULT_MODEL

    task = form.get("task", "transcribe")
    if task not in engine_mod.TASKS:
        task = "transcribe"

    try:
        batch_size = int(form.get("batch_size", "8"))
    except (TypeError, ValueError):
        batch_size = 8
    if batch_size not in (0, 4, 8, 16):
        batch_size = 8

    return {
        "language": language,
        "model": model,
        "task": task,
        "vad": _as_bool(form.get("vad", "true")),
        "word_timestamps": _as_bool(form.get("word_timestamps", "false")),
        "batch_size": batch_size,
    }


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #

BANNER = r"""
   _   _   _ ___  ___ _    ___ ___
  /_\ | | | | _ \/ __| |  |_ _/ __|
 / _ \| |_| |   / (_ | |__ | |\__ \
/_/ \_\\___/|_|_\\___|____|___|___/
"""


def main() -> None:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

    print(BANNER)
    state = "found" if engine_mod.FFMPEG else "NOT FOUND  (install ffmpeg and add it to PATH)"
    print(f"  ffmpeg : {state}")
    print(f"  device : {manager.engine.device} / {manager.engine.compute_type}")
    print(f"  model  : {engine_mod.DEFAULT_MODEL} (default)")
    print(f"  work   : {WORK_DIR}")
    print(f"\n  Open in your browser ->  http://{HOST}:{PORT}\n")

    app = create_app()
    try:
        app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True,
                use_reloader=False)
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
