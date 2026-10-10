# Auralis · Speech → Text Studio

> Auralis is a local web studio that turns audio & video into text with
> [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Drag a file, get a
> timestamped transcript, export TXT/SRT. Fully offline, no cloud.

Auralis turns speech into clean text — right on your machine. Upload an audio or
video file, the app extracts the audio track with ffmpeg, transcribes speech with
Whisper, and returns a neat transcript with timestamps. No file ever leaves your
computer.

## ✨ Features

- 🎧 **Audio → text** with [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- 🎬 **Video → text** — extracts the audio track with ffmpeg first
- 🖱 **Upload** via button or **drag & drop**
- 📊 **Live progress** while processing (Server-Sent Events)
- 📋 **Copy** the result and **export** to **TXT** or **SRT** (with timestamps)
- 🌍 **18 languages** plus automatic language detection
- 🧠 **Model size selection** (tiny → large-v3)
- 🛡 Clear format validation and friendly error messages
- 📱 Responsive, modern interface
- 🔒 **100% local** — everything runs on your machine

## 🧰 Requirements

- **Python 3.9+**
- **ffmpeg** available in `PATH` (used to extract audio from video)
- Internet access on the first run (to download the Whisper model)

## 🚀 Installation

```bash
git clone https://github.com/HardOgur4ik228/Auralis.git
cd Auralis
pip install -r requirements.txt
```

Install **ffmpeg** if you don't have it yet:

| OS      | Command                                                                |
|---------|------------------------------------------------------------------------|
| Windows | https://www.gyan.dev/ffmpeg/builds/ (unpack, add `bin` to PATH)        |
| macOS   | `brew install ffmpeg`                                                  |
| Linux   | `sudo apt install ffmpeg`                                              |

## ▶️ Run

```bash
python auralis.py
```

Then open **http://127.0.0.1:5000** in your browser.
You can also just run `auralis.py` from PyCharm.

## 🕹 Usage

1. Drag an audio/video file onto the drop zone (or click to choose one).
2. Pick the recognition **language** (or leave *Auto-detect*) and the **model size**.
3. Press **Transcribe** and watch the live progress.
4. Copy the text or download it as **TXT** / **SRT**.

Supported formats:

- **Audio:** mp3, wav, m4a, aac, flac, ogg, opus, wma, aiff, amr, mp2, oga, weba
- **Video:** mp4, mkv, mov, avi, webm, flv, wmv, m4v, mpg, mpeg, 3gp, ts, ogv

## ⚙️ Configuration

Optional environment variables:

| Variable          | Default       | Description                          |
|-------------------|---------------|--------------------------------------|
| `AURALIS_HOST`    | `127.0.0.1`   | Host to listen on                    |
| `AURALIS_PORT`    | `5000`        | Port                                 |
| `AURALIS_DEVICE`  | `cpu`         | `cpu`, `cuda` or `auto`              |
| `AURALIS_MODEL`   | `small`       | Default model (`tiny`…`large-v3`)    |
| `AURALIS_DEBUG`   | `0`           | Set to `1` for Flask debug mode      |

## 📁 Project structure

```
Auralis/
├── auralis.py        # the whole app: Flask backend + web UI
├── requirements.txt  # Python dependencies
├── .gitignore
└── README.md
```

Auralis is intentionally a **single-file application** — the Flask backend, the
HTML/CSS/JS interface and all logic live in `auralis.py`.

## 🧪 Troubleshooting

- **"ffmpeg not found" / the button does nothing** — install ffmpeg and make sure
  the `ffmpeg` command works in your terminal.
- **First transcription is slow** — the Whisper model is downloaded once and then
  cached. `large-v3` is the most accurate but the heaviest.
- **`metadata_errors` error from PyAV** — Auralis decodes the WAV itself (stdlib
  `wave` + numpy), so it is not affected by `av` version mismatches.
- **Out of memory with large models** — try `small` or `base`, or run on CPU with
  `int8`.

## 🧱 Tech stack

Python · Flask · faster-whisper · ffmpeg · HTML / CSS / JavaScript

## 📄 License

Released under the MIT License — feel free to add a `LICENSE` file.
