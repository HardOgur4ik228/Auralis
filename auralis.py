# -*- coding: utf-8 -*-
"""
================================================================================
  A U R A L I S  —  Speech -> Text Studio
================================================================================
Однофайловое веб-приложение для преобразования аудио и видео в текст.

Возможности
-----------
  * Распознавание речи из аудиофайлов (faster-whisper).
  * Извлечение аудиодорожки из видео (ffmpeg) и её транскрипция.
  * Загрузка файла кнопкой и перетаскиванием в область (drag & drop).
  * Живой прогресс обработки (Server-Sent Events) и вывод результата.
  * Копирование текста в буфер и сохранение в TXT (а также SRT с таймкодами).
  * Выбор языка распознавания: авто, русский, английский и др.
  * Выбор размера модели Whisper.
  * Проверка форматов, размеров и понятные сообщения об ошибках.
  * Полностью адаптивная вёрстка.

Установка зависимостей
-----------------------
    pip install flask faster-whisper

Отдельно требуется установленный ffmpeg (должен быть доступен в PATH),
иначе извлечение аудио из видео работать не будет.
  Windows: https://www.gyan.dev/ffmpeg/builds/  (распаковать и добавить bin в PATH)
  macOS:   brew install ffmpeg
  Linux:   sudo apt install ffmpeg

Запуск
------
    python auralis.py

Затем откройте в браузере адрес, который будет напечатан в консоли
(по умолчанию http://127.0.0.1:5000).

Переменные окружения (необязательно)
------------------------------------
    AURALIS_HOST=127.0.0.1     адрес прослушивания
    AURALIS_PORT=5000          порт
    AURALIS_DEVICE=cpu         cpu | cuda | auto
    AURALIS_MODEL=small        модель по умолчанию (tiny..large-v3)
    AURALIS_DEBUG=1            режим отладки Flask
================================================================================
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file

# ---------------------------------------------------------------------------- #
#  Конфигурация
# ---------------------------------------------------------------------------- #

BASE_DIR = Path(__file__).resolve().parent
WORK_DIR = BASE_DIR / "auralis_work"
UPLOAD_DIR = WORK_DIR / "uploads"
AUDIO_DIR = WORK_DIR / "audio"
for _d in (UPLOAD_DIR, AUDIO_DIR):
    _d.mkdir(parents=True, exist_ok=True)

HOST = os.environ.get("AURALIS_HOST", "127.0.0.1")
PORT = int(os.environ.get("AURALIS_PORT", "5000"))
DEBUG = os.environ.get("AURALIS_DEBUG", "0") == "1"

MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1 ГБ

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
             ".wma", ".aiff", ".aif", ".amr", ".mp2", ".oga", ".weba"}
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv",
             ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".ogv"}
ALLOWED_EXT = AUDIO_EXT | VIDEO_EXT

MODELS = {
    "tiny":     "Tiny      — очень быстро, базовая точность",
    "base":     "Base      — быстро, средняя точность",
    "small":    "Small     — оптимально (рекомендуется)",
    "medium":   "Medium    — выше точность, медленнее",
    "large-v3": "Large v3  — максимальная точность, требует ресурсов",
}
DEFAULT_MODEL = os.environ.get("AURALIS_MODEL", "small")
if DEFAULT_MODEL not in MODELS:
    DEFAULT_MODEL = "small"

LANGUAGES = [
    ("auto", "Автоопределение"),
    ("ru", "Русский"),
    ("en", "English"),
    ("uk", "Українська"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("pt", "Português"),
    ("pl", "Polski"),
    ("tr", "Türkçe"),
    ("nl", "Nederlands"),
    ("cs", "Čeština"),
    ("ar", "العربية"),
    ("hi", "हिन्दी"),
    ("zh", "中文"),
    ("ja", "日本語"),
    ("ko", "한국어"),
]
LANG_CODES = {code for code, _ in LANGUAGES}

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

# ---------------------------------------------------------------------------- #
#  Хранилище задач
# ---------------------------------------------------------------------------- #

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
MODEL_CACHE: dict[str, object] = {}
MODEL_LOCK = threading.Lock()


def new_job(filename: str, language: str, model: str) -> str:
    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "filename": filename,
            "language": language,
            "model": model,
            "status": "queued",      # queued|extracting|loading|transcribing|done|error
            "progress": 0,
            "message": "Задача создана…",
            "error": None,
            "text": "",
            "segments": [],
            "detected_language": None,
            "language_probability": None,
            "duration": None,
            "created": time.time(),
        }
    return job_id


def snapshot(job: dict) -> dict:
    return {
        "status": job["status"],
        "progress": round(job["progress"], 1),
        "message": job["message"],
        "error": job["error"],
        "filename": job["filename"],
        "detected_language": job["detected_language"],
        "language_probability": job["language_probability"],
        "duration": job["duration"],
    }


# ---------------------------------------------------------------------------- #
#  ffmpeg / ffprobe
# ---------------------------------------------------------------------------- #

def _run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def ffprobe_duration(path: Path) -> float | None:
    if not FFPROBE:
        return None
    try:
        res = _run([
            FFPROBE, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ], timeout=60)
        out = res.stdout.decode("utf-8", "ignore").strip()
        return float(out) if out else None
    except Exception:
        return None


def extract_audio(src: Path, dst: Path) -> None:
    """Извлекает/конвертирует аудиодорожку в WAV 16 kHz mono (PCM s16le)."""
    if not FFMPEG:
        raise RuntimeError(
            "ffmpeg не найден. Установите ffmpeg и добавьте его в PATH."
        )
    res = _run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dst),
    ], timeout=3600)
    if res.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        err = res.stderr.decode("utf-8", "ignore").strip().splitlines()
        tail = err[-1] if err else "неизвестная ошибка"
        raise RuntimeError(f"Не удалось извлечь аудиодорожку: {tail}")


def load_audio_array(path: Path):
    """Читает WAV (16 kHz, mono, s16le) в numpy float32 массив.

    Декодируем сами через стандартный модуль ``wave`` — так мы не зависим от
    версии PyAV, которую faster-whisper использует для чтения файлов.
    """
    import wave
    import numpy as np

    with wave.open(str(path), "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())

    if width != 2:
        raise RuntimeError(f"Неожиданная разрядность WAV: {width * 8} бит")

    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        raise RuntimeError(f"Неожиданная частота дискретизации WAV: {rate} Гц")
    return audio


# ---------------------------------------------------------------------------- #
#  Модель
# ---------------------------------------------------------------------------- #

def resolve_device() -> tuple[str, str]:
    dev = os.environ.get("AURALIS_DEVICE", "cpu").strip().lower()
    if dev == "auto":
        try:
            import ctranslate2  # noqa: WPS433
            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda", "float16"
        except Exception:
            pass
        return "cpu", "int8"
    if dev == "cuda":
        return "cuda", "float16"
    return "cpu", "int8"


def get_model(size: str):
    size = size if size in MODELS else DEFAULT_MODEL
    device, compute = resolve_device()
    key = f"{size}:{device}:{compute}"
    with MODEL_LOCK:
        model = MODEL_CACHE.get(key)
        if model is None:
            from faster_whisper import WhisperModel  # noqa: WPS433
            model = WhisperModel(size, device=device, compute_type=compute)
            MODEL_CACHE[key] = model
        return model


# ---------------------------------------------------------------------------- #
#  Обработка
# ---------------------------------------------------------------------------- #

def _set(job: dict, **fields) -> None:
    with JOBS_LOCK:
        job.update(fields)


def process_job(job_id: str, upload_path: Path) -> None:
    job = JOBS.get(job_id)
    if job is None:
        return
    audio_path = AUDIO_DIR / f"{job_id}.wav"
    try:
        # 1) Извлечение аудио
        _set(job, status="extracting", progress=3,
             message="Извлекаю аудиодорожку…")
        extract_audio(upload_path, audio_path)

        duration = ffprobe_duration(audio_path) or 0.0
        if duration <= 0:
            duration = 0.0
        _set(job, duration=round(duration, 1))

        # 2) Загрузка модели
        _set(job, status="loading", progress=8,
             message=f"Загружаю модель «{job['model']}» "
                     f"(первый раз может занять время)…")
        model = get_model(job["model"])

        # 3) Транскрипция
        _set(job, status="transcribing", progress=12,
             message="Распознаю речь…")

        language = None if job["language"] == "auto" else job["language"]
        audio_data = load_audio_array(audio_path)
        segments_iter, info = model.transcribe(
            audio_data,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=True,
        )

        total = float(getattr(info, "duration", 0.0) or duration or 0.0)
        _set(job,
             detected_language=getattr(info, "language", None),
             language_probability=round(
                 float(getattr(info, "language_probability", 0.0) or 0.0), 3),
             duration=round(total, 1) if total else job["duration"])

        collected = []
        last = time.time()
        for seg in segments_iter:
            text = (seg.text or "").strip()
            if text:
                collected.append({
                    "start": round(float(seg.start), 2),
                    "end": round(float(seg.end), 2),
                    "text": text,
                })
            if total > 0:
                pct = 12 + min(float(seg.end) / total, 1.0) * 85
            else:
                pct = min(90, job["progress"] + 1)
            # обновляем не чаще 4 раз в секунду, чтобы не спамить SSE
            now = time.time()
            if now - last > 0.25:
                _set(job, progress=min(pct, 97), message="Распознаю речь…")
                last = now

        full_text = "\n".join(s["text"] for s in collected).strip()
        if not full_text:
            full_text = ""

        _set(job,
             status="done",
             progress=100,
             message="Готово!" if full_text else "Речь не обнаружена.",
             text=full_text,
             segments=collected)

    except Exception as exc:  # noqa: BLE001
        _set(job, status="error", message="Произошла ошибка.",
             error=str(exc))
    finally:
        for p in (upload_path, audio_path):
            try:
                if p and p.exists():
                    p.unlink()
            except Exception:
                pass


# ---------------------------------------------------------------------------- #
#  Flask
# ---------------------------------------------------------------------------- #

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "Файл слишком большой (максимум 1 ГБ)."}), 413


@app.get("/api/health")
def api_health():
    return jsonify({
        "ffmpeg": bool(FFMPEG),
        "ffprobe": bool(FFPROBE),
        "models": list(MODELS.keys()),
        "default_model": DEFAULT_MODEL,
        "languages": [{"code": c, "name": n} for c, n in LANGUAGES],
        "max_size": MAX_FILE_SIZE,
    })


@app.post("/api/upload")
def api_upload():
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"error": "Файл не выбран."}), 400

    original = f.filename
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXT:
        return jsonify({
            "error": f"Формат «{ext or 'без расширения'}» не поддерживается.",
            "hint": "Аудио: " + ", ".join(sorted(AUDIO_EXT)) +
                    ". Видео: " + ", ".join(sorted(VIDEO_EXT)),
        }), 400

    if not FFMPEG:
        return jsonify({
            "error": "ffmpeg не найден в системе.",
            "hint": "Установите ffmpeg и добавьте его в PATH, затем "
                    "перезапустите приложение.",
        }), 500

    language = request.form.get("language", "auto")
    if language not in LANG_CODES:
        language = "auto"
    model = request.form.get("model", DEFAULT_MODEL)
    if model not in MODELS:
        model = DEFAULT_MODEL

    job_id = new_job(original, language, model)
    upload_path = UPLOAD_DIR / f"{job_id}{ext}"
    f.save(str(upload_path))

    if upload_path.stat().st_size == 0:
        upload_path.unlink(missing_ok=True)
        return jsonify({"error": "Загруженный файл пустой."}), 400

    threading.Thread(
        target=process_job, args=(job_id, upload_path), daemon=True
    ).start()
    return jsonify({"job_id": job_id, "filename": original})


@app.get("/api/events/<job_id>")
def api_events(job_id: str):
    def gen():
        last_payload = None
        while True:
            job = JOBS.get(job_id)
            if job is None:
                yield "data: " + json.dumps(
                    {"status": "error", "message": "Задача не найдена."},
                    ensure_ascii=False) + "\n\n"
                break
            payload = json.dumps(snapshot(job), ensure_ascii=False)
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            if job["status"] in ("done", "error"):
                break
            time.sleep(0.35)

    return Response(gen(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


@app.get("/api/result/<job_id>")
def api_result(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        return jsonify({"error": "Задача не найдена."}), 404
    return jsonify({
        "status": job["status"],
        "text": job["text"],
        "segments": job["segments"],
        "detected_language": job["detected_language"],
        "language_probability": job["language_probability"],
        "duration": job["duration"],
        "filename": job["filename"],
    })


def _fmt_ts(seconds: float, srt: bool = True) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if srt:
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def _build_srt(segments: list[dict]) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_ts(seg['start'])} --> {_fmt_ts(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


@app.get("/api/download/<job_id>")
def api_download(job_id: str):
    job = JOBS.get(job_id)
    if job is None or job["status"] != "done":
        return jsonify({"error": "Результат ещё не готов."}), 404

    fmt = request.args.get("fmt", "txt").lower()
    stem = Path(job["filename"]).stem or "transcript"
    if fmt == "srt":
        data = _build_srt(job["segments"])
        name, mime = f"{stem}.srt", "application/x-subrip; charset=utf-8"
    else:
        data = (job["text"] or "") + "\n"
        name, mime = f"{stem}.txt", "text/plain; charset=utf-8"

    buf = io.BytesIO(data.encode("utf-8"))
    return send_file(buf, mimetype=mime, as_attachment=True,
                     download_name=name)


@app.get("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html; charset=utf-8")


# ---------------------------------------------------------------------------- #
#  Интерфейс (HTML + CSS + JS в одном шаблоне)
# ---------------------------------------------------------------------------- #

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auralis · Speech → Text Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --ink:#06070f;
  --ink-2:#0b0d1c;
  --panel:rgba(21,23,44,.62);
  --panel-solid:#12142a;
  --line:rgba(150,160,230,.14);
  --line-strong:rgba(150,160,230,.28);
  --text:#eef1ff;
  --muted:#9aa3c6;
  --muted-2:#6f7799;
  --primary:#6d5efc;
  --primary-2:#9a8bff;
  --coral:#ff7a59;
  --mint:#2ee6c6;
  --danger:#ff5c78;
  --ok:#3ddc97;
  --shadow:0 24px 60px -28px rgba(0,0,0,.85);
  --radius:22px;
  --font-display:"Space Grotesk","Inter",system-ui,Segoe UI,Roboto,sans-serif;
  --font-body:"Inter",system-ui,Segoe UI,Roboto,sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,Consolas,monospace;
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  font-family:var(--font-body);
  color:var(--text);
  background:var(--ink);
  -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;
  overflow-x:hidden;
}
/* ---- фон: aurora + сетка ---- */
.bg{position:fixed;inset:0;z-index:-2;overflow:hidden;background:
  radial-gradient(1200px 700px at 12% -10%, rgba(109,94,252,.30), transparent 60%),
  radial-gradient(1000px 700px at 100% 0%, rgba(46,230,198,.16), transparent 55%),
  radial-gradient(900px 800px at 60% 120%, rgba(255,122,89,.20), transparent 60%),
  linear-gradient(180deg,#06070f, #0a0b18 60%, #06070f);
}
.bg::after{
  content:"";position:absolute;inset:-30%;
  background:conic-gradient(from 0deg at 50% 50%,
    rgba(109,94,252,.0), rgba(109,94,252,.10), rgba(46,230,198,.10),
    rgba(255,122,89,.10), rgba(109,94,252,0));
  animation:spin 42s linear infinite;filter:blur(60px);opacity:.7;
}
.grid-overlay{position:fixed;inset:0;z-index:-1;pointer-events:none;
  background-image:
    linear-gradient(rgba(150,160,230,.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(150,160,230,.045) 1px, transparent 1px);
  background-size:44px 44px;
  mask-image:radial-gradient(ellipse at 50% 30%, #000 0%, transparent 78%);
  -webkit-mask-image:radial-gradient(ellipse at 50% 30%, #000 0%, transparent 78%);
}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
@keyframes pulseGlow{0%,100%{opacity:.55}50%{opacity:1}}
@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}
@keyframes bars{0%,100%{transform:scaleY(.35)}50%{transform:scaleY(1)}}
@keyframes floaty{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes spin360{to{transform:rotate(360deg)}}

.shell{max-width:1240px;margin:0 auto;padding:26px 22px 60px}

/* ---- header ---- */
.topbar{display:flex;align-items:center;justify-content:space-between;
  gap:18px;padding:8px 4px 26px}
.brand{display:flex;align-items:center;gap:14px}
.brand-mark{width:52px;height:52px;border-radius:16px;flex:none;position:relative;
  background:linear-gradient(140deg,var(--primary),var(--primary-2) 45%,var(--coral));
  display:grid;place-items:center;box-shadow:0 12px 30px -12px rgba(109,94,252,.9)}
.brand-mark::after{content:"";position:absolute;inset:0;border-radius:16px;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.22)}
.brand-mark .eq{display:flex;align-items:center;gap:3px;height:24px}
.brand-mark .eq i{display:block;width:4px;border-radius:3px;background:#fff;
  transform-origin:center;animation:bars 1.15s ease-in-out infinite}
.brand-mark .eq i:nth-child(1){height:12px;animation-delay:0s}
.brand-mark .eq i:nth-child(2){height:22px;animation-delay:.12s}
.brand-mark .eq i:nth-child(3){height:16px;animation-delay:.24s}
.brand-mark .eq i:nth-child(4){height:24px;animation-delay:.36s}
.brand-mark .eq i:nth-child(5){height:13px;animation-delay:.48s}
.brand-name{font-family:var(--font-display);font-weight:700;font-size:22px;
  letter-spacing:.06em;line-height:1}
.brand-sub{display:block;color:var(--muted-2);font-size:11.5px;letter-spacing:.22em;
  text-transform:uppercase;margin-top:5px;font-weight:500}
.topbar-actions{display:flex;align-items:center;gap:12px}
.pill{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:999px;
  border:1px solid var(--line);background:var(--panel);backdrop-filter:blur(10px);
  color:var(--muted);font-size:12.5px;font-weight:500;white-space:nowrap}
.dot{width:8px;height:8px;border-radius:50%;background:var(--muted-2);flex:none;
  box-shadow:0 0 0 3px rgba(111,119,153,.18)}
.dot.ok{background:var(--ok);box-shadow:0 0 0 3px rgba(61,220,151,.18)}
.dot.bad{background:var(--danger);box-shadow:0 0 0 3px rgba(255,92,120,.18)}
.ghost-btn{border:1px solid var(--line);background:transparent;color:var(--text);
  padding:9px 15px;border-radius:999px;font-family:var(--font-body);font-size:13px;
  font-weight:500;cursor:pointer;transition:.22s}
.ghost-btn:hover{border-color:var(--line-strong);background:rgba(255,255,255,.05)}

/* ---- hero ---- */
.hero{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;
  gap:20px;margin:6px 0 26px}
.hero h1{font-family:var(--font-display);font-weight:700;font-size:clamp(28px,4.6vw,46px);
  line-height:1.04;margin:0;letter-spacing:-.02em;max-width:16ch}
.hero h1 .grad{background:linear-gradient(100deg,var(--primary-2),var(--mint) 55%,var(--coral));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{color:var(--muted);margin:14px 0 0;max-width:52ch;font-size:15px;line-height:1.6}
.chips{display:flex;flex-wrap:wrap;gap:9px;margin-top:2px}
.chip{padding:7px 13px;border-radius:999px;border:1px solid var(--line);
  background:rgba(255,255,255,.03);color:var(--muted);font-size:12.5px}
.chip b{color:var(--text);font-weight:600}

/* ---- layout ---- */
.grid{display:grid;grid-template-columns:minmax(0,430px) minmax(0,1fr);gap:22px;
  align-items:start}
.panel{position:relative;background:var(--panel);border:1px solid var(--line);
  border-radius:var(--radius);backdrop-filter:blur(16px);box-shadow:var(--shadow);
  padding:22px;animation:rise .6s cubic-bezier(.2,.7,.2,1) both}
.panel::before{content:"";position:absolute;inset:0;border-radius:inherit;padding:1px;
  background:linear-gradient(150deg,rgba(255,255,255,.16),transparent 40%,transparent 65%,rgba(109,94,252,.25));
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
  -webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none;opacity:.9}
.panel.output{animation-delay:.08s}
.panel-head{display:flex;align-items:center;gap:12px;margin-bottom:18px}
.step{font-family:var(--font-mono);font-size:12px;font-weight:500;color:var(--primary-2);
  border:1px solid var(--line-strong);border-radius:9px;padding:5px 9px;letter-spacing:.08em}
.panel-head h2{font-family:var(--font-display);font-size:17px;font-weight:600;margin:0;letter-spacing:.01em}
.panel-head .sub{color:var(--muted-2);font-size:12.5px;margin-left:auto}

/* ---- dropzone ---- */
.drop{position:relative;border:1.6px dashed var(--line-strong);border-radius:18px;
  padding:30px 20px;text-align:center;cursor:pointer;transition:.25s;
  background:radial-gradient(120% 120% at 50% 0%, rgba(109,94,252,.09), transparent 60%);
  overflow:hidden}
.drop:hover{border-color:rgba(154,139,255,.55);transform:translateY(-2px)}
.drop.drag{border-color:var(--mint);background:radial-gradient(120% 120% at 50% 0%, rgba(46,230,198,.16), transparent 65%)}
.drop .ico{width:60px;height:60px;margin:0 auto 14px;border-radius:18px;display:grid;place-items:center;
  background:linear-gradient(150deg,rgba(109,94,252,.28),rgba(46,230,198,.16));border:1px solid var(--line);
  animation:floaty 4.5s ease-in-out infinite}
.drop .ico svg{width:28px;height:28px;stroke:#fff;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.drop h3{margin:0 0 6px;font-family:var(--font-display);font-size:16px;font-weight:600}
.drop p{margin:0;color:var(--muted);font-size:13px}
.drop .hint{margin-top:12px;color:var(--muted-2);font-size:11.5px;letter-spacing:.03em}
.file-meta{display:none;align-items:center;gap:12px;margin-top:14px;padding:12px 14px;
  border-radius:14px;border:1px solid var(--line);background:rgba(109,94,252,.10)}
.file-meta.show{display:flex;animation:rise .35s both}
.file-meta .fi{width:38px;height:38px;border-radius:11px;flex:none;display:grid;place-items:center;
  background:linear-gradient(150deg,var(--primary),var(--coral));font-family:var(--font-mono);font-size:10px;font-weight:600}
.file-meta .fn{font-size:13.5px;font-weight:500;word-break:break-all;line-height:1.3}
.file-meta .fs{color:var(--muted-2);font-size:11.5px;font-family:var(--font-mono)}
.file-meta .x{margin-left:auto;border:none;background:transparent;color:var(--muted);cursor:pointer;
  font-size:18px;line-height:1;padding:4px 6px;border-radius:8px;transition:.2s}
.file-meta .x:hover{color:var(--danger);background:rgba(255,92,120,.12)}

/* ---- form ---- */
.field{margin-top:18px}
.field label{display:block;font-size:12px;color:var(--muted);letter-spacing:.06em;
  text-transform:uppercase;font-weight:600;margin-bottom:8px}
.select{width:100%;appearance:none;background:rgba(9,10,22,.7);color:var(--text);
  border:1px solid var(--line);border-radius:13px;padding:13px 40px 13px 15px;font-size:14px;
  font-family:var(--font-body);cursor:pointer;transition:.2s;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%239aa3c6' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>");
  background-repeat:no-repeat;background-position:right 15px center}
.select:hover{border-color:var(--line-strong)}
.select:focus{outline:none;border-color:var(--primary-2);box-shadow:0 0 0 4px rgba(109,94,252,.16)}
.select option{background:#12142a;color:#eef1ff}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}

/* ---- primary button ---- */
.btn{width:100%;margin-top:22px;border:none;border-radius:15px;padding:15px 18px;cursor:pointer;
  font-family:var(--font-display);font-size:15px;font-weight:600;letter-spacing:.02em;color:#fff;
  background:linear-gradient(100deg,var(--primary),var(--primary-2) 55%,var(--coral));
  background-size:180% 100%;transition:.3s;position:relative;overflow:hidden;
  display:flex;align-items:center;justify-content:center;gap:10px;
  box-shadow:0 16px 34px -16px rgba(109,94,252,.85)}
.btn:hover:not(:disabled){background-position:100% 0;transform:translateY(-2px);
  box-shadow:0 22px 42px -16px rgba(109,94,252,.95)}
.btn:active:not(:disabled){transform:translateY(0)}
.btn:disabled{opacity:.45;cursor:not-allowed;filter:saturate(.6)}
.btn .arw{transition:transform .3s}
.btn:hover:not(:disabled) .arw{transform:translateX(4px)}

/* ---- output / progress ---- */
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;
  text-align:center;padding:40px 20px;color:var(--muted);min-height:340px}
.empty .wave{display:flex;align-items:center;gap:5px;height:70px;margin-bottom:22px}
.empty .wave i{width:6px;border-radius:6px;
  background:linear-gradient(180deg,var(--primary-2),var(--mint));opacity:.75;
  animation:bars 1.5s ease-in-out infinite}
.empty .wave i:nth-child(1){height:22px;animation-delay:0s}
.empty .wave i:nth-child(2){height:44px;animation-delay:.1s}
.empty .wave i:nth-child(3){height:64px;animation-delay:.2s}
.empty .wave i:nth-child(4){height:36px;animation-delay:.3s}
.empty .wave i:nth-child(5){height:56px;animation-delay:.4s}
.empty .wave i:nth-child(6){height:28px;animation-delay:.5s}
.empty .wave i:nth-child(7){height:48px;animation-delay:.6s}
.empty h3{font-family:var(--font-display);color:var(--text);font-size:16px;margin:0 0 8px}
.empty p{margin:0;max-width:38ch;font-size:13.5px;line-height:1.6}

.progress-wrap{display:none}
.progress-wrap.show{display:block;animation:rise .4s both}
.prog-top{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:10px}
.prog-label{font-family:var(--font-display);font-size:15px;font-weight:600}
.prog-pct{font-family:var(--font-mono);font-size:24px;font-weight:500;
  background:linear-gradient(100deg,var(--primary-2),var(--mint));-webkit-background-clip:text;
  background-clip:text;color:transparent}
.bar{height:10px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden;position:relative;
  border:1px solid var(--line)}
.bar>span{display:block;height:100%;width:0;border-radius:999px;
  background:linear-gradient(90deg,var(--primary),var(--mint) 70%,var(--coral));
  background-size:200% 100%;animation:shimmer 2s linear infinite;transition:width .4s cubic-bezier(.3,.7,.2,1)}
.status-line{display:flex;align-items:center;gap:10px;margin-top:14px;color:var(--muted);font-size:13.5px}
.spinner{width:16px;height:16px;border-radius:50%;flex:none;
  border:2px solid rgba(255,255,255,.18);border-top-color:var(--mint);animation:spin360 .8s linear infinite}
.prog-meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.meta-tag{font-family:var(--font-mono);font-size:11.5px;color:var(--muted);
  border:1px solid var(--line);border-radius:8px;padding:5px 9px;background:rgba(255,255,255,.03)}
.meta-tag b{color:var(--mint);font-weight:500}

.alert{display:none;gap:12px;margin-top:16px;padding:14px 16px;border-radius:14px;
  border:1px solid rgba(255,92,120,.35);background:rgba(255,92,120,.10);color:#ffd7de;font-size:13.5px;line-height:1.5}
.alert.show{display:flex;animation:rise .3s both}
.alert .ai{flex:none;font-size:16px}

/* ---- result ---- */
.result{display:none}
.result.show{display:block;animation:rise .45s both}
.tabs{display:flex;gap:6px;padding:5px;border-radius:13px;border:1px solid var(--line);
  background:rgba(9,10,22,.55);margin-bottom:14px;width:fit-content}
.tab{border:none;background:transparent;color:var(--muted);font-family:var(--font-body);
  font-size:13px;font-weight:500;padding:8px 15px;border-radius:9px;cursor:pointer;transition:.2s}
.tab.active{color:#fff;background:linear-gradient(100deg,var(--primary),var(--primary-2));
  box-shadow:0 8px 18px -10px rgba(109,94,252,.9)}
.txt-box{white-space:pre-wrap;word-wrap:break-word;line-height:1.7;font-size:14.5px;
  background:rgba(9,10,22,.55);border:1px solid var(--line);border-radius:15px;padding:18px;
  max-height:46vh;overflow:auto;min-height:120px}
.seg-list{max-height:46vh;overflow:auto;border:1px solid var(--line);border-radius:15px;
  background:rgba(9,10,22,.55)}
.seg{display:grid;grid-template-columns:96px 1fr;gap:14px;padding:12px 16px;
  border-bottom:1px solid rgba(150,160,230,.08)}
.seg:last-child{border-bottom:none}
.seg:hover{background:rgba(109,94,252,.07)}
.seg .ts{font-family:var(--font-mono);font-size:11.5px;color:var(--mint);padding-top:2px;white-space:nowrap}
.seg .tx{font-size:14px;line-height:1.55;color:var(--text)}
.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.act{display:inline-flex;align-items:center;gap:9px;border:1px solid var(--line);
  background:rgba(255,255,255,.04);color:var(--text);padding:11px 16px;border-radius:12px;
  font-family:var(--font-body);font-size:13.5px;font-weight:500;cursor:pointer;transition:.2s}
.act:hover{border-color:var(--line-strong);background:rgba(255,255,255,.08);transform:translateY(-1px)}
.act.primary{background:linear-gradient(100deg,var(--primary),var(--primary-2));border:none}
.act svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.result-stats{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}

/* ---- modal ---- */
.modal{position:fixed;inset:0;z-index:50;display:none;align-items:center;justify-content:center;padding:22px;
  background:rgba(4,5,12,.72);backdrop-filter:blur(6px)}
.modal.show{display:flex;animation:rise .25s both}
.modal-card{max-width:640px;width:100%;max-height:86vh;overflow:auto;background:var(--panel-solid);
  border:1px solid var(--line-strong);border-radius:20px;padding:26px;box-shadow:var(--shadow)}
.modal-card h3{font-family:var(--font-display);margin:0 0 6px;font-size:20px}
.modal-card p{color:var(--muted);font-size:14px;line-height:1.65}
.modal-card h4{font-family:var(--font-display);font-size:14px;margin:20px 0 8px;color:var(--text)}
.modal-card code{font-family:var(--font-mono);font-size:12.5px;background:rgba(109,94,252,.14);
  border:1px solid var(--line);border-radius:7px;padding:2px 7px}
.modal-card pre{background:#0a0b16;border:1px solid var(--line);border-radius:12px;padding:14px;
  overflow:auto;font-family:var(--font-mono);font-size:12.5px;color:#c9d1ff;margin:8px 0}
.modal-close{margin-top:20px}

/* ---- toast ---- */
.toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(20px);
  opacity:0;pointer-events:none;z-index:60;padding:13px 20px;border-radius:13px;
  border:1px solid var(--line-strong);background:rgba(18,20,42,.95);backdrop-filter:blur(10px);
  font-size:13.5px;transition:.3s;box-shadow:var(--shadow)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.ok{border-color:rgba(61,220,151,.5)}
.toast.err{border-color:rgba(255,92,120,.5)}

.foot{margin-top:30px;text-align:center;color:var(--muted-2);font-size:12px;letter-spacing:.02em}
.foot b{color:var(--muted);font-weight:500}

/* ---- responsive ---- */
@media (max-width:980px){
  .grid{grid-template-columns:1fr}
}
@media (max-width:600px){
  .shell{padding:18px 14px 44px}
  .topbar{flex-wrap:wrap}
  .brand-sub{display:none}
  .hero{margin-bottom:18px}
  .panel{padding:17px}
  .two{grid-template-columns:1fr}
  .seg{grid-template-columns:1fr;gap:4px}
  .empty{min-height:260px}
  .tabs{width:100%}
  .tab{flex:1}
}
@media (prefers-reduced-motion:reduce){
  *{animation:none!important;transition:none!important}
}
</style>
</head>
<body>
<div class="bg"></div>
<div class="grid-overlay"></div>

<div class="shell">
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark"><div class="eq"><i></i><i></i><i></i><i></i><i></i></div></div>
      <div>
        <span class="brand-name">AURALIS</span>
        <span class="brand-sub">Speech → Text Studio</span>
      </div>
    </div>
    <div class="topbar-actions">
      <span class="pill"><span class="dot" id="healthDot"></span><span id="healthText">проверка…</span></span>
      <button class="ghost-btn" id="helpBtn">Как запустить</button>
    </div>
  </header>

  <section class="hero">
    <div>
      <h1>Звук в <span class="grad">чистый</span> текст</h1>
      <p>Загрузите аудио или видео — Auralis извлечёт дорожку, распознает речь
         и вернёт аккуратный текст с таймкодами. Работает локально, ничего не
         уходит в облако.</p>
    </div>
    <div class="chips">
      <span class="chip"><b>faster-whisper</b></span>
      <span class="chip">100+ языков</span>
      <span class="chip">TXT / SRT</span>
      <span class="chip">Локально</span>
    </div>
  </section>

  <div class="grid">
    <!-- INPUT -->
    <section class="panel">
      <div class="panel-head">
        <span class="step">01</span>
        <h2>Источник</h2>
      </div>

      <div class="drop" id="drop" role="button" tabindex="0" aria-label="Загрузить аудио или видео файл">
        <div class="ico">
          <svg viewBox="0 0 24 24"><path d="M12 16V4M12 4l-4 4M12 4l4 4"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
        </div>
        <h3>Перетащите файл сюда</h3>
        <p>или нажмите, чтобы выбрать</p>
        <div class="hint">Аудио: mp3 · wav · m4a · flac · ogg · opus &nbsp;•&nbsp; Видео: mp4 · mkv · mov · webm</div>
        <input type="file" id="fileInput" hidden
               accept=".mp3,.wav,.m4a,.aac,.flac,.ogg,.opus,.wma,.aiff,.aif,.amr,.mp2,.oga,.weba,.mp4,.mkv,.mov,.avi,.webm,.flv,.wmv,.m4v,.mpg,.mpeg,.3gp,.ts,.ogv">
      </div>

      <div class="file-meta" id="fileMeta">
        <div class="fi" id="fileExt">FILE</div>
        <div style="min-width:0">
          <div class="fn" id="fileName">—</div>
          <div class="fs" id="fileSize">—</div>
        </div>
        <button class="x" id="fileClear" title="Убрать">×</button>
      </div>

      <div class="field two">
        <div>
          <label for="langSel">Язык</label>
          <select class="select" id="langSel"></select>
        </div>
        <div>
          <label for="modelSel">Модель</label>
          <select class="select" id="modelSel"></select>
        </div>
      </div>

      <button class="btn" id="startBtn" disabled>
        Распознать <span class="arw">→</span>
      </button>
    </section>

    <!-- OUTPUT -->
    <section class="panel output">
      <div class="panel-head">
        <span class="step">02</span>
        <h2>Результат</h2>
        <span class="sub" id="outSub">ожидание файла</span>
      </div>

      <!-- empty state -->
      <div class="empty" id="emptyState">
        <div class="wave"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
        <h3>Здесь появится транскрипт</h3>
        <p>Выберите файл слева и нажмите «Распознать». Прогресс и текст будут
           показаны на этой панели.</p>
      </div>

      <!-- progress -->
      <div class="progress-wrap" id="progressWrap">
        <div class="prog-top">
          <div class="prog-label" id="progLabel">Обработка…</div>
          <div class="prog-pct" id="progPct">0%</div>
        </div>
        <div class="bar"><span id="barFill"></span></div>
        <div class="status-line"><span class="spinner" id="spinner"></span><span id="statusText">…</span></div>
        <div class="prog-meta" id="progMeta"></div>
        <div class="alert" id="errBox"><span class="ai">⚠</span><span id="errText"></span></div>
      </div>

      <!-- result -->
      <div class="result" id="result">
        <div class="result-stats" id="resultStats"></div>
        <div class="tabs">
          <button class="tab active" data-tab="text">Текст</button>
          <button class="tab" data-tab="segs">Таймкоды</button>
        </div>
        <div id="paneText"><div class="txt-box" id="textOut"></div></div>
        <div id="paneSegs" style="display:none"><div class="seg-list" id="segOut"></div></div>
        <div class="actions">
          <button class="act primary" id="copyBtn">
            <svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>Копировать текст</button>
          <button class="act" id="txtBtn">
            <svg viewBox="0 0 24 24"><path d="M12 3v12M12 15l-4-4M12 15l4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>Скачать TXT</button>
          <button class="act" id="srtBtn">
            <svg viewBox="0 0 24 24"><path d="M12 3v12M12 15l-4-4M12 15l4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>Скачать SRT</button>
          <button class="act" id="againBtn">
            <svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>Новый файл</button>
        </div>
      </div>
    </section>
  </div>

  <div class="foot">Auralis · локальная транскрипция на базе <b>faster-whisper</b> и <b>ffmpeg</b></div>
</div>

<!-- modal -->
<div class="modal" id="helpModal">
  <div class="modal-card">
    <h3>Быстрый старт</h3>
    <p>Auralis — одностраничное приложение. Ниже — минимальная инструкция по запуску.</p>

    <h4>1. Установите зависимости</h4>
    <pre>pip install flask faster-whisper</pre>

    <h4>2. Установите ffmpeg</h4>
    <p>Нужен для извлечения аудио из видео. Убедитесь, что команда <code>ffmpeg</code>
       доступна в PATH.</p>
    <pre>Windows : https://www.gyan.dev/ffmpeg/builds/
macOS   : brew install ffmpeg
Linux   : sudo apt install ffmpeg</pre>

    <h4>3. Запустите</h4>
    <pre>python auralis.py</pre>
    <p>Откройте <code>http://127.0.0.1:5000</code> в браузере.</p>

    <h4>Примечания</h4>
    <p>При первом распознавании модель Whisper скачивается автоматически — это
       может занять несколько минут. Модель <code>large-v3</code> требует больше
       памяти и времени. Для GPU задайте переменную окружения
       <code>AURALIS_DEVICE=cuda</code>.</p>

    <button class="ghost-btn modal-close" id="modalClose">Понятно</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
(function(){
  "use strict";
  const $ = (s) => document.querySelector(s);
  const state = { file:null, jobId:null, es:null, text:"", segments:[] };

  /* ---------- утилиты ---------- */
  function fmtSize(bytes){
    if(bytes < 1024) return bytes + " B";
    const u = ["KB","MB","GB"]; let i = -1, n = bytes;
    do { n /= 1024; i++; } while(n >= 1024 && i < u.length-1);
    return n.toFixed(n < 10 ? 1 : 0) + " " + u[i];
  }
  function fmtTime(sec){
    sec = Math.max(0, Math.round(sec||0));
    const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = sec%60;
    const p = (v)=>String(v).padStart(2,"0");
    return (h>0 ? p(h)+":" : "") + p(m)+":"+p(s);
  }
  let toastTimer;
  function toast(msg, kind){
    const t = $("#toast");
    t.textContent = msg;
    t.className = "toast show " + (kind||"");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(()=>{ t.className = "toast " + (kind||""); }, 2600);
  }

  /* ---------- health / options ---------- */
  fetch("/api/health").then(r=>r.json()).then(d=>{
    const dot = $("#healthDot"), txt = $("#healthText");
    if(d.ffmpeg){ dot.classList.add("ok"); txt.textContent = "ffmpeg готов"; }
    else { dot.classList.add("bad"); txt.textContent = "нет ffmpeg"; }

    const ls = $("#langSel");
    d.languages.forEach(l=>{
      const o = document.createElement("option");
      o.value = l.code; o.textContent = l.name;
      ls.appendChild(o);
    });
    ls.value = "auto";

    const ms = $("#modelSel");
    d.models.forEach(m=>{
      const o = document.createElement("option");
      o.value = m; o.textContent = m;
      ms.appendChild(o);
    });
    ms.value = d.default_model || "small";
  }).catch(()=>{
    $("#healthDot").classList.add("bad");
    $("#healthText").textContent = "нет связи";
  });

  /* ---------- выбор файла ---------- */
  const drop = $("#drop"), fileInput = $("#fileInput");

  drop.addEventListener("click", ()=> fileInput.click());
  drop.addEventListener("keydown", (e)=>{
    if(e.key === "Enter" || e.key === " " || e.key === "Spacebar"){
      e.preventDefault(); fileInput.click();
    }
  });
  fileInput.addEventListener("change", ()=>{ if(fileInput.files[0]) setFile(fileInput.files[0]); });

  ["dragenter","dragover"].forEach(ev=>{
    drop.addEventListener(ev, (e)=>{ e.preventDefault(); drop.classList.add("drag"); });
  });
  ["dragleave","dragend","drop"].forEach(ev=>{
    drop.addEventListener(ev, ()=> drop.classList.remove("drag"));
  });
  drop.addEventListener("drop", (e)=>{
    e.preventDefault();
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if(f) setFile(f);
  });
  // блокируем открытие файла браузером при промахе мимо зоны
  ["dragover","drop"].forEach(ev=>{
    window.addEventListener(ev, (e)=> e.preventDefault());
  });

  const AUDIO = ["mp3","wav","m4a","aac","flac","ogg","opus","wma","aiff","aif","amr","mp2","oga","weba"];
  const VIDEO = ["mp4","mkv","mov","avi","webm","flv","wmv","m4v","mpg","mpeg","3gp","ts","ogv"];
  const MAX = 1024*1024*1024;

  function setFile(f){
    const ext = (f.name.split(".").pop()||"").toLowerCase();
    if(!AUDIO.includes(ext) && !VIDEO.includes(ext)){
      toast("Формат ." + ext + " не поддерживается", "err"); return;
    }
    if(f.size > MAX){ toast("Файл больше 1 ГБ", "err"); return; }

    state.file = f;
    $("#fileExt").textContent = ext.slice(0,4).toUpperCase();
    $("#fileName").textContent = f.name;
    $("#fileSize").textContent = fmtSize(f.size) + " · " + (VIDEO.includes(ext) ? "видео" : "аудио");
    $("#fileMeta").classList.add("show");
    $("#startBtn").disabled = false;
    resetOutput();
  }

  $("#fileClear").addEventListener("click", (e)=>{
    e.stopPropagation();
    state.file = null; fileInput.value = "";
    $("#fileMeta").classList.remove("show");
    $("#startBtn").disabled = true;
    resetOutput();
  });

  /* ---------- вывод / состояния ---------- */
  function resetOutput(){
    $("#emptyState").style.display = "";
    $("#progressWrap").classList.remove("show");
    $("#result").classList.remove("show");
    $("#errBox").classList.remove("show");
    $("#barFill").style.width = "0%";
    $("#progPct").textContent = "0%";
    $("#outSub").textContent = state.file ? "готово к запуску" : "ожидание файла";
  }

  function showError(msg){
    $("#errBox").classList.add("show");
    $("#errText").textContent = msg;
    $("#spinner").style.display = "none";
  }

  /* ---------- запуск ---------- */
  $("#startBtn").addEventListener("click", ()=>{
    if(!state.file) return;
    start();
  });

  function start(){
    const fd = new FormData();
    fd.append("file", state.file);
    fd.append("language", $("#langSel").value);
    fd.append("model", $("#modelSel").value);

    $("#emptyState").style.display = "none";
    $("#result").classList.remove("show");
    $("#errBox").classList.remove("show");
    $("#spinner").style.display = "";
    $("#progressWrap").classList.add("show");
    $("#progLabel").textContent = "Загрузка файла…";
    $("#statusText").textContent = "Передаю файл на сервер…";
    $("#progPct").textContent = "0%";
    $("#barFill").style.width = "0%";
    $("#progMeta").innerHTML = "";
    $("#startBtn").disabled = true;
    $("#outSub").textContent = "обработка";

    fetch("/api/upload", { method:"POST", body: fd })
      .then(async (r)=>{
        const d = await r.json().catch(()=>({}));
        if(!r.ok){ throw new Error(d.error || "Ошибка загрузки"); }
        state.jobId = d.job_id;
        listen(d.job_id);
      })
      .catch(err=>{
        showError(err.message);
        $("#progLabel").textContent = "Ошибка";
        $("#startBtn").disabled = false;
        $("#outSub").textContent = "ошибка";
      });
  }

  function listen(id){
    if(state.es){ state.es.close(); }
    const es = new EventSource("/api/events/" + id);
    state.es = es;

    es.onmessage = (ev)=>{
      let d; try{ d = JSON.parse(ev.data); }catch(_){ return; }
      updateProgress(d);
      if(d.status === "done"){
        es.close(); state.es = null;
        if(d.message === "Речь не обнаружена." || !d.text){
          fetchResult(id, d);
        } else {
          fetchResult(id, d);
        }
      } else if(d.status === "error"){
        es.close(); state.es = null;
        showError(d.error || "Неизвестная ошибка");
        $("#progLabel").textContent = "Ошибка";
        $("#startBtn").disabled = false;
        $("#outSub").textContent = "ошибка";
      }
    };
    es.onerror = ()=>{
      // если поток закрылся штатно после завершения — не показываем ошибку
      if(state.es){ /* оставим на повтор */ }
    };
  }

  function updateProgress(d){
    const pct = Math.round(d.progress||0);
    $("#barFill").style.width = pct + "%";
    $("#progPct").textContent = pct + "%";
    $("#statusText").textContent = d.message || "…";
    const labels = { extracting:"Извлечение аудио", loading:"Загрузка модели",
                     transcribing:"Распознавание", queued:"В очереди", done:"Готово" };
    if(labels[d.status]) $("#progLabel").textContent = labels[d.status];

    const meta = [];
    if(d.duration) meta.push('<span class="meta-tag">длительность: <b>' + fmtTime(d.duration) + '</b></span>');
    if(d.detected_language) meta.push('<span class="meta-tag">язык: <b>' + d.detected_language + '</b></span>');
    if(d.language_probability) meta.push('<span class="meta-tag">уверенность: <b>' + Math.round(d.language_probability*100) + '%</b></span>');
    $("#progMeta").innerHTML = meta.join("");
  }

  function fetchResult(id, d){
    fetch("/api/result/" + id).then(r=>r.json()).then(res=>{
      state.text = res.text || "";
      state.segments = res.segments || [];
      renderResult(res);
    }).catch(()=>{ showError("Не удалось получить результат"); });
  }

  function renderResult(res){
    $("#progressWrap").classList.remove("show");
    $("#startBtn").disabled = false;
    $("#outSub").textContent = "готово";

    if(!res.text){
      $("#emptyState").style.display = "";
      $("#emptyState").querySelector("h3").textContent = "Речь не обнаружена";
      $("#emptyState").querySelector("p").textContent =
        "В файле не найдено распознаваемой речи. Попробуйте другой файл или модель.";
      return;
    }

    const stats = [];
    stats.push('<span class="meta-tag">слов: <b>' + res.text.split(/\s+/).filter(Boolean).length + '</b></span>');
    if(res.duration) stats.push('<span class="meta-tag">длительность: <b>' + fmtTime(res.duration) + '</b></span>');
    if(res.detected_language) stats.push('<span class="meta-tag">язык: <b>' + res.detected_language + '</b></span>');
    stats.push('<span class="meta-tag">фрагментов: <b>' + res.segments.length + '</b></span>');
    $("#resultStats").innerHTML = stats.join("");

    $("#textOut").textContent = res.text;

    const segOut = $("#segOut");
    segOut.innerHTML = "";
    res.segments.forEach(s=>{
      const row = document.createElement("div"); row.className = "seg";
      const ts = document.createElement("div"); ts.className = "ts";
      ts.textContent = fmtTime(s.start) + " → " + fmtTime(s.end);
      const tx = document.createElement("div"); tx.className = "tx";
      tx.textContent = s.text;
      row.appendChild(ts); row.appendChild(tx);
      segOut.appendChild(row);
    });

    $("#result").classList.add("show");
    toast("Транскрипция готова", "ok");
  }

  /* ---------- табы ---------- */
  document.querySelectorAll(".tab").forEach(tab=>{
    tab.addEventListener("click", ()=>{
      document.querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
      tab.classList.add("active");
      const t = tab.dataset.tab;
      $("#paneText").style.display = (t === "text") ? "" : "none";
      $("#paneSegs").style.display = (t === "segs") ? "" : "none";
    });
  });

  /* ---------- действия ---------- */
  function copyText(){
    const txt = state.text;
    if(!txt){ toast("Нечего копировать", "err"); return; }
    const done = ()=>{ toast("Текст скопирован", "ok"); };
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(txt).then(done).catch(()=>fallbackCopy(txt, done));
    } else { fallbackCopy(txt, done); }
  }
  function fallbackCopy(txt, done){
    const ta = document.createElement("textarea");
    ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try{ document.execCommand("copy"); done(); }
    catch(_){ toast("Не удалось скопировать", "err"); }
    document.body.removeChild(ta);
  }
  $("#copyBtn").addEventListener("click", copyText);

  function dl(fmt){
    if(!state.jobId){ toast("Результат не готов", "err"); return; }
    window.location.href = "/api/download/" + state.jobId + "?fmt=" + fmt;
  }
  $("#txtBtn").addEventListener("click", ()=> dl("txt"));
  $("#srtBtn").addEventListener("click", ()=> dl("srt"));
  $("#againBtn").addEventListener("click", ()=>{
    state.file = null; fileInput.value = "";
    $("#fileMeta").classList.remove("show");
    $("#startBtn").disabled = true;
    window.scrollTo({ top:0, behavior:"smooth" });
    resetOutput();
  });

  /* ---------- модалка ---------- */
  $("#helpBtn").addEventListener("click", ()=> $("#helpModal").classList.add("show"));
  $("#modalClose").addEventListener("click", ()=> $("#helpModal").classList.remove("show"));
  $("#helpModal").addEventListener("click", (e)=>{ if(e.target.id === "helpModal") e.currentTarget.classList.remove("show"); });
  document.addEventListener("keydown", (e)=>{ if(e.key === "Escape") $("#helpModal").classList.remove("show"); });
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------- #
#  Точка входа
# ---------------------------------------------------------------------------- #

BANNER = r"""
   ___                        _ _
  / _ \ _   _ _ __ __ _ _ __ (_) |___
 | |_| | | | | '__/ _` | '_ \| | / __|
 |  _  | |_| | | | (_| | | | | | \__ \
 |_| |_|\__,_|_|  \__,_|_| |_|_|_|___/

  Speech -> Text Studio  ·  faster-whisper + Flask
"""


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    print(BANNER)
    print(f"  ffmpeg : {'найден' if FFMPEG else 'НЕ НАЙДЕН — установите и добавьте в PATH'}")
    print(f"  модель : {DEFAULT_MODEL}  (по умолчанию)")
    print(f"  папка  : {WORK_DIR}")
    print(f"\n  Откройте в браузере:  http://{HOST}:{PORT}\n")

    try:
        app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True,
                use_reloader=False)
    except KeyboardInterrupt:
        print("\n  Остановлено пользователем.")


if __name__ == "__main__":
    main()
