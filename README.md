# Auralis · Speech → Text Studio

> A local web studio that turns audio & video into text with
> [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Drag a file, get a
> timestamped transcript, export TXT/SRT/VTT/JSON. Fully offline, no cloud.

Auralis pairs a **Python/Flask backend** with a **clean HTML/CSS/JS frontend**.
Upload an audio or video file, the backend extracts the audio track with
`ffmpeg`, transcribes speech with Whisper and streams live progress back to the
browser over Server-Sent Events. Nothing ever leaves your machine.

## ✨ Features

- 🎧 **Audio → text** with faster-whisper
- 🎬 **Video → text** — the audio track is extracted with ffmpeg first
- 🖱 **Upload** by button or **drag & drop**
- 📊 **Live progress** streamed over SSE, with a stage-by-stage stepper
- 🌍 **19 languages** + automatic language detection
- 🧠 **Model selection** from `tiny` to `large-v3`
- 🔁 **Task**: transcribe *or* translate to English
- ⚡ **Batched inference** (configurable batch size) for faster long files
- 🎚 Advanced options: voice-activity filter and word-level timestamps
- 👀 **Client-side waveform preview** (Web Audio API, decoded in the browser)
- 📋 **Copy** the result and **export** to **TXT · SRT · VTT · JSON**
- 🌗 **Dark / light theme**, RU/EN interface, responsive layout
- 🛡 Clear format validation, friendly localised errors, cancelable jobs
- 🔒 **100% local** — no cloud, no telemetry

## 🧰 Requirements

- **Python 3.9+**
- **ffmpeg** available on `PATH` (used to extract audio from video)
- Internet access on the first run (to download the chosen Whisper model)

## 🚀 Installation

```bash
git clone https://github.com/HardOgur4ik228/Auralis.git
cd Auralis
pip install -r requirements.txt
```

Install **ffmpeg** if you don't have it yet:

| OS      | Command                                                          |
|---------|------------------------------------------------------------------|
| Windows | https://www.gyan.dev/ffmpeg/builds/ (unpack, add `bin` to PATH)  |
| macOS   | `brew install ffmpeg`                                            |
| Linux   | `sudo apt install ffmpeg`                                        |

## ▶️ Run

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

### Running from PyCharm

1. `File → Open…` and choose the project folder.
2. Create/select an interpreter and install `requirements.txt`
   (PyCharm usually offers a one-click **Install requirements** banner).
3. Open `app.py`, click the green ▶ next to `if __name__ == "__main__"`.
4. Browse to the URL printed in the run console.

## 🕹 Usage

1. Drag an audio/video file onto the drop zone (or click to browse).
2. Pick the **language**, **model** and **task**; open **Advanced** if needed.
3. Press **Transcribe** and watch the live progress.
4. Copy the text or download it as **TXT / SRT / VTT / JSON**.

Supported formats:

- **Audio:** mp3, wav, m4a, aac, flac, ogg, opus, wma, aiff, amr, mp2, oga, weba
- **Video:** mp4, mkv, mov, avi, webm, flv, wmv, m4v, mpg, mpeg, 3gp, ts, ogv

## ⚙️ Configuration

Optional environment variables:

| Variable          | Default        | Description                              |
|-------------------|----------------|------------------------------------------|
| `AURALIS_HOST`    | `127.0.0.1`    | Host to listen on                        |
| `AURALIS_PORT`    | `5000`         | Port                                     |
| `AURALIS_DEVICE`  | `cpu`          | `cpu`, `cuda` or `auto`                  |
| `AURALIS_MODEL`   | `small`        | Default model (`tiny`…`large-v3`)        |
| `AURALIS_MAX_JOBS`| `2`            | Max concurrent transcriptions            |
| `AURALIS_JOB_TTL` | `3600`         | Seconds a finished job is kept in memory |
| `AURALIS_MAX_UPLOAD` | `1073741824` | Max upload size in bytes (1 GB)        |
| `AURALIS_DEBUG`   | `0`            | `1` enables Flask debug mode             |

## 🔌 API

| Method | Endpoint                          | Purpose                          |
|--------|-----------------------------------|----------------------------------|
| `GET`  | `/api/health`                     | Capabilities, models, languages  |
| `POST` | `/api/jobs`                       | Upload a file, start a job       |
| `GET`  | `/api/jobs/<id>`                  | Full job result (JSON)           |
| `GET`  | `/api/jobs/<id>/stream`           | Live progress (SSE)              |
| `GET`  | `/api/jobs/<id>/download?format=` | Export `txt`/`srt`/`vtt`/`json`  |
| `DELETE` | `/api/jobs/<id>`                | Cancel / remove a job            |

## 📁 Project structure

```
Auralis/
├── app.py               # Flask web layer: routes, validation, SSE, downloads
├── transcription.py     # Engine: ffmpeg, faster-whisper, jobs, exports
├── templates/
│   └── index.html       # Semantic markup
├── static/
│   ├── css/styles.css   # Design system, themes, animations, responsive
│   ├── js/app.js        # i18n, upload, SSE, results, exports
│   └── favicon.svg
├── requirements.txt
├── LICENSE
└── README.md
```

## 🧪 Troubleshooting

- **`ffmpeg` not found / the button does nothing** — install ffmpeg and make sure
  the `ffmpeg` command works in your terminal.
- **First transcription is slow** — the Whisper model is downloaded once and then
  cached. `large-v3` is the most accurate but the heaviest.
- **`metadata_errors` error from PyAV** — Auralis decodes the WAV itself (stdlib
  `wave` + numpy), so it is unaffected by `av` version mismatches.
- **Out of memory with large models** — try `small` or `base`, lower the batch
  size, or run on CPU with `int8`.

## 🧱 Tech stack

Python · Flask · faster-whisper · ffmpeg · HTML · CSS · JavaScript

## 📄 License

Released under the [MIT License](LICENSE).
