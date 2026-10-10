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

## 🌐 Deployment — static frontend (Pages / GitHub Pages) + a Python host

The UI is plain HTML/CSS/JS, but the backend is **Python + faster-whisper (ML)
+ ffmpeg**. Static hosts cannot execute Python (and a Worker/Edge runtime has
no room for a Whisper model), so use a two-part setup:

```
public/                      →  Cloudflare Pages or GitHub Pages   (static site)
app.py + transcription.py    →  Python host        (Render / Fly.io / HF Spaces / VPS)
```

The browser UI calls the backend over HTTPS. CORS is already enabled in
`app.py`. Only one setting needs your backend URL — see step 3.

### 1 · Backend on Render (easiest)

1. Push this repo to GitHub.
2. Go to **render.com → New → Blueprint** and connect the repo
   (or New → Web Service and pick the `Dockerfile`).
3. Render builds the container: Python + ffmpeg + faster-whisper.
4. Default env vars from `render.yaml`: `AURALIS_MODEL=base`,
   `AURALIS_DEVICE=cpu`, `AURALIS_MAX_JOBS=1`.
5. Copy the service URL, e.g. `https://auralis-api.onrender.com`.

### 2 · Frontend on Cloudflare Pages

**Via dashboard (recommended):**

1. **Workers & Pages → Create → Pages → Connect to Git** → pick the repo.
2. Framework preset: **None**.
3. **Build command:** leave **empty** — there is nothing to compile.
4. **Build output directory:** `public`.
5. Deploy. Every push to `main` redeploys; pull requests automatically get
   their own **preview URL**.

**Deploy / preview commands (equivalent, via the CLI):**

```bash
# production build on Pages (usually not needed — dashboard does this for you)
echo "static site — nothing to build"

# production deploy  (dashboard equivalent)
npx wrangler pages deploy public --project-name auralis-web --branch main

# preview deploy
npx wrangler pages deploy public --project-name auralis-web --branch preview
```

> Cloudflare Pages itself has no separate "Deploy command" and "Preview
> command" fields — deploys are automatic from Git and previews are automatic
> per branch/PR. The commands above reproduce that behaviour from your machine.

### 2b · Frontend on GitHub Pages (optional alternative)

GitHub Pages serves the site from a **subpath**: for this repo the URL is
`https://<your-username>.github.io/Auralis/`. That is why `public/index.html`
uses **relative** asset paths (`css/styles.css`, `js/app.js`), which work both
at the local root and inside the subpath.

**Deploy from a branch (recommended, no extra permissions):**

1. `Settings → Pages → Build and deployment → Source: *Deploy from a branch*`
   → Branch: `gh-pages` → folder `/ (root)` → Save.
2. The `gh-pages` branch is already in the repo with the site at its root.
3. Wait ~1 minute, then open `https://<your-username>.github.io/Auralis/`.

To re-deploy after changing `public/`, run from the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy-gh-pages.ps1
```

**Auto-deploy on every push (requires GitHub *workflow* scope):**

1. Copy `docs/gh-pages-autodeploy.yml.example` to `.github/workflows/pages.yml`
   and push. GitHub rejects this push until your token has the **workflow**
   scope — re-authenticate with `gh auth login --scopes workflow`.
2. `Settings → Pages → Source: *GitHub Actions*`.
3. Every push to `main` re-deploys automatically.

> Manual alternative: `git subtree push --prefix public origin gh-pages`
> revives/re-writes the `gh-pages` branch from `public/` without a script.

### 3 · Point the frontend at the API

In `public/index.html`:

```js
window.AURALIS = { apiBase: "" };   // "" = same server (local run)
```

Replace the empty string with your backend URL:

```js
window.AURALIS = { apiBase: "https://auralis-api.onrender.com" };
```

Push the change — Pages redeploys and the app works from any browser.

### Notes & limits

- Free tiers **sleep after idle**: the first request is slow (cold start).
- Start with model `base` or `small`; `large-v3` needs a lot of RAM.
- The model downloads on the first transcription (takes a minute or two).
- The upload limit is 1 GB (`AURALIS_MAX_UPLOAD`); hosting platforms usually
  allow less per request, so keep files moderate.

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

> On hosting platforms the listening port is injected as `$PORT` and takes
> priority over `AURALIS_PORT`; `AURALIS_HOST` defaults to `0.0.0.0` in the
> Docker image.

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
├── docs/gh-pages-autodeploy.yml.example   # GitHub Actions workflow (move to .github/workflows/ to activate)
├── scripts/deploy-gh-pages.ps1            # publish public/ -> gh-pages branch (no workflow scope needed)
├── public/              # static site — deployed to Cloudflare Pages / GitHub Pages
│   ├── index.html       # markup + client config (window.AURALIS.apiBase)
│   ├── css/styles.css   # design system, themes, responsive
│   ├── js/app.js        # i18n, upload, SSE, results, exports
│   └── favicon.svg
├── app.py               # Flask web layer: routes, validation, SSE, CORS
├── transcription.py     # Engine: ffmpeg, faster-whisper, jobs, exports
├── Dockerfile           # container for the API (Render / Fly.io / …)
├── render.yaml          # one-click Render blueprint
├── requirements.txt     # flask + faster-whisper + gunicorn
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
