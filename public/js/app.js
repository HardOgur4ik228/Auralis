/* =============================================================================
   Auralis — client application
   No frameworks. Handles i18n, theme, upload, SSE progress, results & exports.
   ========================================================================== */

(() => {
  "use strict";

  /* --------------------------------------------------------------------- *
   *  i18n
   * --------------------------------------------------------------------- */
  const I18N = {
    en: {
      "brand.tag": "Speech → Text Studio",
      "status.checking": "Checking server…",
      "status.ready": "Ready",
      "status.noffmpeg": "ffmpeg missing",
      "status.offline": "Server offline",
      "action.help": "How to run",
      "action.start": "Transcribe",
      "action.cancel": "Cancel",
      "action.retry": "Try again",
      "action.copy": "Copy text",
      "action.download": "Download",
      "action.copied": "Copied to clipboard",
      "action.copyFail": "Could not copy",
      "action.new": "New file",

      "hero.eyebrow": "Local transcription engine",
      "hero.line1": "Turn voice into",
      "hero.line2": "clean text",
      "hero.sub": "Drop an audio or video file. Auralis extracts the track, transcribes it with faster-whisper and hands you a tidy transcript with timestamps — entirely on your machine.",
      "hero.tag1": "faster-whisper",
      "hero.tag2": "100+ languages",
      "hero.tag3": "TXT · SRT · VTT · JSON",
      "hero.tag4": "Runs offline",

      "source.title": "Source",
      "source.sub": "Pick a file and set the options",
      "source.note": "Everything runs locally — nothing is uploaded to any cloud.",

      "drop.aria": "Upload an audio or video file",
      "drop.title": "Drag & drop a file here",
      "drop.hint": "or click to browse",
      "drop.formats": "Audio: {a} · Video: {v}",
      "drop.remove": "Remove",

      "wave.caption": "Audio preview · waveform",

      "field.language": "Language",
      "field.model": "Model",
      "field.task": "Task",
      "field.advanced": "Advanced settings",
      "task.transcribe": "Transcribe",
      "task.translate": "Translate to English",
      "opt.vad": "Voice activity filter",
      "opt.vadHint": "Skip silence for cleaner results",
      "opt.words": "Word-level timestamps",
      "opt.wordsHint": "Precise timing for each word",
      "opt.batch": "Batch size",
      "opt.batchOff": "Off · sequential",
      "opt.batchHint": "Batched inference speeds up long files",

      "studio.title": "Studio",
      "studio.idle": "Waiting for a file",
      "studio.ready": "Ready to start",
      "studio.processing": "Processing…",
      "studio.done": "Completed",
      "studio.error": "Failed",
      "studio.canceled": "Canceled",

      "empty.title": "Your transcript appears here",
      "empty.sub": "Choose a file on the left and press Transcribe. Live progress and the result show up in this panel.",
      "emptyResult.title": "No speech detected",
      "emptyResult.sub": "No recognisable speech was found in this file. Try another file or a larger model.",

      "step.extract": "Extract audio",
      "step.load": "Load model",
      "step.transcribe": "Transcribe",

      "msg.queued": "Queued…",
      "msg.extracting": "Extracting the audio track…",
      "msg.loading": "Loading the model (first run downloads it)…",
      "msg.transcribing": "Transcribing speech…",
      "msg.done": "Done!",
      "msg.doneEmpty": "No speech detected.",
      "msg.canceled": "Canceled.",

      "err.title": "Something went wrong",
      "err.details": "Technical details",
      "err.ffmpeg_missing": "ffmpeg was not found on this system. Install it and restart the server.",
      "err.extract_failed": "Could not read the audio track from this file.",
      "err.model_failed": "Could not load the speech model.",
      "err.audio_decode_failed": "Could not decode the extracted audio.",
      "err.empty_file": "The uploaded file is empty.",
      "err.too_large": "The file is too large.",
      "err.invalid_format": "This file format is not supported.",
      "err.no_file": "No file was selected.",
      "err.not_ready": "The result is not ready yet.",
      "err.job_not_found": "This job no longer exists.",
      "err.server_error": "The server hit an unexpected error.",
      "err.network": "Could not reach the server.",
      "err.unknown": "An unexpected error occurred.",

      "tab.text": "Text",
      "tab.timeline": "Timeline",

      "fmt.txt": "Plain text",
      "fmt.srt": "Subtitles",
      "fmt.vtt": "Web subtitles",
      "fmt.json": "Full data",

      "stat.words": "words",
      "stat.chars": "characters",
      "stat.duration": "duration",
      "stat.segments": "segments",
      "stat.speed": "speed",
      "stat.lang": "language",
      "stat.rtf": "× realtime",

      "toast.ready": "Transcription completed",
      "toast.removed": "File removed",
      "toast.canceled": "Job canceled",
      "toast.cannotStart": "Choose a valid file first",

      "footer.built": "Built with",
      "footer.local": "Runs 100% locally",

      "help.title": "Quick start",
      "help.reqTitle": "Requirements",
      "help.req": "Python 3.9+ and ffmpeg available on PATH.",
      "help.installTitle": "1 · Install dependencies",
      "help.ffmpegTitle": "2 · Install ffmpeg",
      "help.runTitle": "3 · Run",
      "help.run": "Then open http://127.0.0.1:5000 in your browser. You can also run app.py directly from PyCharm.",
      "help.notesTitle": "Notes",
      "help.notes": "The Whisper model downloads automatically on first use. large-v3 is the most accurate but the heaviest. Set AURALIS_DEVICE=cuda to use a GPU.",
    },
    ru: {
      "brand.tag": "Речь → Текст",
      "status.checking": "Проверка сервера…",
      "status.ready": "Готово",
      "status.noffmpeg": "нет ffmpeg",
      "status.offline": "Сервер недоступен",
      "action.help": "Как запустить",
      "action.start": "Распознать",
      "action.cancel": "Отменить",
      "action.retry": "Повторить",
      "action.copy": "Копировать текст",
      "action.download": "Скачать",
      "action.copied": "Скопировано в буфер",
      "action.copyFail": "Не удалось скопировать",
      "action.new": "Новый файл",

      "hero.eyebrow": "Локальный движок распознавания",
      "hero.line1": "Превратите голос в",
      "hero.line2": "чистый текст",
      "hero.sub": "Перетащите аудио или видео. Auralis извлечёт дорожку, распознает речь через faster-whisper и вернёт аккуратный транскрипт с таймкодами — целиком на вашем компьютере.",
      "hero.tag1": "faster-whisper",
      "hero.tag2": "100+ языков",
      "hero.tag3": "TXT · SRT · VTT · JSON",
      "hero.tag4": "Работает офлайн",

      "source.title": "Источник",
      "source.sub": "Выберите файл и настройте параметры",
      "source.note": "Всё работает локально — ничего не отправляется в облако.",

      "drop.aria": "Загрузить аудио или видео",
      "drop.title": "Перетащите файл сюда",
      "drop.hint": "или нажмите, чтобы выбрать",
      "drop.formats": "Аудио: {a} · Видео: {v}",
      "drop.remove": "Убрать",

      "wave.caption": "Предпросмотр · осциллограмма",

      "field.language": "Язык",
      "field.model": "Модель",
      "field.task": "Задача",
      "field.advanced": "Дополнительно",
      "task.transcribe": "Распознавание",
      "task.translate": "Перевод на английский",
      "opt.vad": "Фильтр тишины",
      "opt.vadHint": "Пропускать паузы для чистого результата",
      "opt.words": "Тайминги по словам",
      "opt.wordsHint": "Точное время каждого слова",
      "opt.batch": "Размер пакета",
      "opt.batchOff": "Выкл. · последовательно",
      "opt.batchHint": "Пакетная обработка ускоряет длинные файлы",

      "studio.title": "Студия",
      "studio.idle": "Ожидание файла",
      "studio.ready": "Готово к запуску",
      "studio.processing": "Обработка…",
      "studio.done": "Завершено",
      "studio.error": "Ошибка",
      "studio.canceled": "Отменено",

      "empty.title": "Здесь появится транскрипт",
      "empty.sub": "Выберите файл слева и нажмите «Распознать». Прогресс и результат появятся на этой панели.",
      "emptyResult.title": "Речь не обнаружена",
      "emptyResult.sub": "В файле не найдено распознаваемой речи. Попробуйте другой файл или модель побольше.",

      "step.extract": "Извлечение аудио",
      "step.load": "Загрузка модели",
      "step.transcribe": "Распознавание",

      "msg.queued": "В очереди…",
      "msg.extracting": "Извлекаю аудиодорожку…",
      "msg.loading": "Загружаю модель (первый запуск скачает её)…",
      "msg.transcribing": "Распознаю речь…",
      "msg.done": "Готово!",
      "msg.doneEmpty": "Речь не обнаружена.",
      "msg.canceled": "Отменено.",

      "err.title": "Что-то пошло не так",
      "err.details": "Технические детали",
      "err.ffmpeg_missing": "ffmpeg не найден в системе. Установите его и перезапустите сервер.",
      "err.extract_failed": "Не удалось извлечь аудиодорожку из файла.",
      "err.model_failed": "Не удалось загрузить модель распознавания.",
      "err.audio_decode_failed": "Не удалось декодировать извлечённое аудио.",
      "err.empty_file": "Загруженный файл пустой.",
      "err.too_large": "Файл слишком большой.",
      "err.invalid_format": "Такой формат файла не поддерживается.",
      "err.no_file": "Файл не выбран.",
      "err.not_ready": "Результат ещё не готов.",
      "err.job_not_found": "Задача больше не существует.",
      "err.server_error": "На сервере произошла ошибка.",
      "err.network": "Не удалось связаться с сервером.",
      "err.unknown": "Произошла непредвиденная ошибка.",

      "tab.text": "Текст",
      "tab.timeline": "Таймкоды",

      "fmt.txt": "Обычный текст",
      "fmt.srt": "Субтитры",
      "fmt.vtt": "Веб-субтитры",
      "fmt.json": "Полные данные",

      "stat.words": "слов",
      "stat.chars": "символов",
      "stat.duration": "длительность",
      "stat.segments": "фрагментов",
      "stat.speed": "скорость",
      "stat.lang": "язык",
      "stat.rtf": "× к реальному времени",

      "toast.ready": "Распознавание завершено",
      "toast.removed": "Файл убран",
      "toast.canceled": "Задача отменена",
      "toast.cannotStart": "Сначала выберите корректный файл",

      "footer.built": "Сделано на",
      "footer.local": "Работает полностью локально",

      "help.title": "Быстрый старт",
      "help.reqTitle": "Требования",
      "help.req": "Python 3.9+ и ffmpeg, доступный в PATH.",
      "help.installTitle": "1 · Установите зависимости",
      "help.ffmpegTitle": "2 · Установите ffmpeg",
      "help.runTitle": "3 · Запустите",
      "help.run": "Затем откройте http://127.0.0.1:5000 в браузере. Можно также запустить app.py прямо из PyCharm.",
      "help.notesTitle": "Заметки",
      "help.notes": "Модель Whisper скачивается автоматически при первом использовании. large-v3 — самая точная, но тяжёлая. Задайте AURALIS_DEVICE=cuda для GPU.",
    },
  };

  const STAGE_ORDER = ["extracting", "loading", "transcribing"];
  const STAGE_MESSAGE = {
    queued: "msg.queued",
    extracting: "msg.extracting",
    loading: "msg.loading",
    transcribing: "msg.transcribing",
  };

  /* --------------------------------------------------------------------- *
   *  State & helpers
   * --------------------------------------------------------------------- */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const state = {
    file: null,
    jobId: null,
    es: null,
    result: null,
    lang: localStorage.getItem("auralis.lang") || "en",
    health: null,
    finished: false,
    peaks: null,
    emptyKind: "idle",
  };

  const t = (key, vars) => {
    let s = (I18N[state.lang] && I18N[state.lang][key]) || I18N.en[key] || key;
    if (vars) for (const k in vars) s = s.replace(`{${k}}`, vars[k]);
    return s;
  };

  // API base. On Cloudflare Pages the UI lives on one host and the Flask
  // backend on another, so the frontend must know where the API is.
  const API_BASE = (window.AURALIS && window.AURALIS.apiBase)
    ? String(window.AURALIS.apiBase).replace(/\/+$/, "")
    : "";

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    const units = ["KB", "MB", "GB"];
    let value = bytes, i = -1;
    do { value /= 1024; i++; } while (value >= 1024 && i < units.length - 1);
    return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`;
  }

  function formatTime(seconds) {
    seconds = Math.max(0, Math.round(seconds || 0));
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return (h > 0 ? `${pad(h)}:` : "") + `${pad(m)}:${pad(s)}`;
  }

  const extOf = (name) => (name.split(".").pop() || "").toLowerCase();

  /* --------------------------------------------------------------------- *
   *  Toasts
   * --------------------------------------------------------------------- */
  function toast(message, kind = "info", timeout = 3200) {
    const box = $("#toasts");
    const el = document.createElement("div");
    el.className = `toast toast--${kind}`;
    const ico = kind === "ok" ? "✓" : kind === "err" ? "!" : "i";
    el.innerHTML = `<span class="toast__ico">${ico}</span><span></span>`;
    el.lastElementChild.textContent = message;
    box.appendChild(el);
    setTimeout(() => {
      el.classList.add("is-out");
      setTimeout(() => el.remove(), 320);
    }, timeout);
  }

  /* --------------------------------------------------------------------- *
   *  Theme & language
   * --------------------------------------------------------------------- */
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("auralis.theme", theme);
  }

  function initTheme() {
    const saved = localStorage.getItem("auralis.theme");
    const prefersLight = window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: light)").matches;
    applyTheme(saved || (prefersLight ? "light" : "dark"));
    $("#themeBtn").addEventListener("click", () => {
      const now = document.documentElement.getAttribute("data-theme");
      applyTheme(now === "dark" ? "light" : "dark");
      if (state.result) renderResult(state.result);
    });
  }

  function applyI18n() {
    document.documentElement.lang = state.lang;
    $$("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const value = t(key);
      if (value && value !== key) el.textContent = value;
    });
    $$("[data-i18n-aria]").forEach((el) => {
      el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
    });
    $("#fileRemove").setAttribute("aria-label", t("drop.remove"));
    $$(".segment__btn").forEach((b) =>
      b.classList.toggle("is-active", b.dataset.lang === state.lang));
    localStorage.setItem("auralis.lang", state.lang);
    if (state.health) populateOptions();
    renderFormatsLine();
    updateStatusText();
    refreshEmptyText();
    if (state.result) renderResult(state.result);
  }

  function setLang(lang) {
    state.lang = I18N[lang] ? lang : "en";
    applyI18n();
  }

  function initLang() {
    $$(".segment__btn").forEach((btn) =>
      btn.addEventListener("click", () => setLang(btn.dataset.lang)));
  }

  /* --------------------------------------------------------------------- *
   *  Server health
   * --------------------------------------------------------------------- */
  function updateStatusText() {
    const pill = $("#statusPill");
    const text = $("#statusText");
    if (!state.health) {
      text.textContent = t("status.offline");
      pill.classList.remove("is-ok"); pill.classList.add("is-bad");
      return;
    }
    if (state.health.ffmpeg) {
      text.textContent = t("status.ready");
      pill.classList.add("is-ok"); pill.classList.remove("is-bad");
      pill.title = `device: ${state.health.device} · compute: ${state.health.compute_type}`;
    } else {
      text.textContent = t("status.noffmpeg");
      pill.classList.remove("is-ok"); pill.classList.add("is-bad");
      pill.title = "Install ffmpeg and restart the server";
    }
  }

  async function fetchHealth() {
    try {
      const res = await fetch(API_BASE + "/api/health");
      if (!res.ok) throw new Error("health failed");
      state.health = await res.json();
      populateOptions();
      renderFormatsLine();
    } catch (e) {
      state.health = null;
    }
    updateStatusText();
  }

  function renderFormatsLine() {
    if (!state.health) return;
    const audio = state.health.audio_ext.slice(0, 6).map((e) => e.slice(1)).join(" · ");
    const video = state.health.video_ext.slice(0, 4).map((e) => e.slice(1)).join(" · ");
    $("#formatsLine").textContent = t("drop.formats", { a: audio, v: video });
  }

  function populateOptions() {
    if (!state.health) return;

    const langSel = $("#langSelect");
    const prevLang = langSel.value || "auto";
    langSel.innerHTML = "";
    state.health.languages.forEach((l) => {
      const opt = document.createElement("option");
      opt.value = l.code;
      opt.textContent = l[state.lang] || l.en;
      langSel.appendChild(opt);
    });
    langSel.value = [...langSel.options].some((o) => o.value === prevLang) ? prevLang : "auto";

    const modelSel = $("#modelSelect");
    if (!modelSel.options.length) {
      state.health.models.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        modelSel.appendChild(opt);
      });
      modelSel.value = state.health.default_model || "small";
    }
  }

  /* --------------------------------------------------------------------- *
   *  File selection
   * --------------------------------------------------------------------- */
  const AUDIO_EXT = () => (state.health ? state.health.audio_ext : []);
  const VIDEO_EXT = () => (state.health ? state.health.video_ext : []);

  function validateFile(file) {
    const ext = "." + extOf(file.name);
    const allowed = [...AUDIO_EXT(), ...VIDEO_EXT()];
    if (allowed.length && !allowed.includes(ext)) return "invalid_format";
    if (state.health && file.size > state.health.max_upload) return "too_large";
    return null;
  }

  function setFile(file) {
    const err = validateFile(file);
    if (err) { toast(t("err." + err), "err"); return; }

    state.file = file;
    const ext = extOf(file.name);
    const isVideo = VIDEO_EXT().includes("." + ext);
    $("#fileExt").textContent = ext.slice(0, 4).toUpperCase();
    $("#fileName").textContent = file.name;
    $("#fileSize").textContent = `${formatBytes(file.size)} · ${isVideo ? "video" : "audio"}`;
    $("#fileChip").hidden = false;
    $("#startBtn").disabled = false;
    $("#studioSub").textContent = t("studio.ready");
    showEmptyState("idle");
    renderWaveform(file);
  }

  function clearFile() {
    state.file = null;
    $("#fileInput").value = "";
    $("#fileChip").hidden = true;
    $("#waveform").hidden = true;
    $("#startBtn").disabled = true;
    state.peaks = null;
    showEmptyState("idle");
  }

  function initDropzone() {
    const dz = $("#dropzone");
    const input = $("#fileInput");

    dz.addEventListener("click", () => input.click());
    dz.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
    });
    input.addEventListener("change", () => { if (input.files[0]) setFile(input.files[0]); });

    ["dragenter", "dragover"].forEach((ev) =>
      dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("is-drag"); }));
    ["dragleave", "dragend", "drop"].forEach((ev) =>
      dz.addEventListener(ev, () => dz.classList.remove("is-drag")));
    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) setFile(f);
    });
    ["dragover", "drop"].forEach((ev) =>
      window.addEventListener(ev, (e) => e.preventDefault()));

    $("#fileRemove").addEventListener("click", () => { clearFile(); toast(t("toast.removed"), "info"); });
  }

  /* ---- client-side waveform preview (real decode via Web Audio) ---- */
  async function renderWaveform(file) {
    const wrap = $("#waveform");
    const canvas = $("#waveCanvas");
    const ext = "." + extOf(file.name);
    if (!AUDIO_EXT().includes(ext) || file.size > 80 * 1024 * 1024) {
      wrap.hidden = true; state.peaks = null; return;
    }
    let ctx;
    try {
      const buffer = await file.arrayBuffer();
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      const audio = await ctx.decodeAudioData(buffer);
      state.peaks = computePeaks(audio.getChannelData(0), 720);
      wrap.hidden = false;
      drawPeaks(canvas, state.peaks);
    } catch (e) {
      wrap.hidden = true; state.peaks = null;
    } finally {
      if (ctx && ctx.close) ctx.close();
    }
  }

  function computePeaks(data, buckets) {
    const peaks = new Float32Array(buckets);
    const step = Math.max(1, Math.floor(data.length / buckets));
    for (let i = 0; i < buckets; i++) {
      let max = 0;
      const start = i * step;
      for (let j = 0; j < step; j += 24) {
        const v = Math.abs(data[start + j] || 0);
        if (v > max) max = v;
      }
      peaks[i] = max;
    }
    return peaks;
  }

  function drawPeaks(canvas, peaks) {
    if (!peaks) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.parentElement.clientWidth - 28;
    const h = 72;
    canvas.width = Math.max(1, w * dpr);
    canvas.height = h * dpr;
    canvas.style.width = "100%";
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const grad = ctx.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, "#6f6bff");
    grad.addColorStop(0.5, "#38bdf8");
    grad.addColorStop(1, "#22d3ee");
    ctx.fillStyle = grad;
    const barW = w / peaks.length;
    const mid = h / 2;
    for (let i = 0; i < peaks.length; i++) {
      const bh = Math.max(1.2, peaks[i] * mid * 0.94);
      ctx.fillRect(i * barW + barW * 0.18, mid - bh, Math.max(1, barW * 0.64), bh * 2);
    }
  }

  /* --------------------------------------------------------------------- *
   *  Studio states
   * --------------------------------------------------------------------- */
  function refreshEmptyText() {
    const box = $("#stateEmpty");
    if (!box) return;
    const noSpeech = state.emptyKind === "noSpeech";
    box.querySelector("h3").textContent = t(noSpeech ? "emptyResult.title" : "empty.title");
    box.querySelector("p").textContent = t(noSpeech ? "emptyResult.sub" : "empty.sub");
  }

  function showEmptyState(kind = "idle") {
    state.emptyKind = kind;
    refreshEmptyText();
    showState("empty");
  }

  function showState(name) {
    $("#stateEmpty").hidden = name !== "empty";
    $("#stateProgress").hidden = name !== "progress";
    $("#stateError").hidden = name !== "error";
    $("#stateResult").hidden = name !== "result";
  }

  function setStepper(status) {
    const idx = STAGE_ORDER.indexOf(status);
    $$(".stepper__item").forEach((item) => {
      const i = STAGE_ORDER.indexOf(item.dataset.stage);
      item.classList.toggle("is-done", idx > i || status === "done");
      item.classList.toggle("is-active", idx === i);
    });
  }

  function setProgress(snap) {
    const pct = Math.round(snap.progress || 0);
    $("#progressFill").style.width = pct + "%";
    $("#progressPct").innerHTML = `${pct}<small>%</small>`;
    const key = STAGE_MESSAGE[snap.status] || "msg.queued";
    $("#progressStatus").textContent = snap.message_code === "done"
      ? t("msg.done") : t(key);
    setStepper(snap.status);

    const meta = [];
    if (snap.duration) meta.push(metaChip(t("stat.duration"), formatTime(snap.duration)));
    if (snap.detected_language) meta.push(metaChip(t("stat.lang"), snap.detected_language));
    $("#progressMeta").innerHTML = meta.join("");
  }

  const metaChip = (label, value) => `<span class="meta-chip">${label}: <b>${escapeHtml(String(value))}</b></span>`;

  /* --------------------------------------------------------------------- *
   *  Job lifecycle
   * --------------------------------------------------------------------- */
  function readOptions() {
    return {
      language: $("#langSelect").value,
      model: $("#modelSelect").value,
      task: $("#taskSelect").value,
      vad: $("#optVad").checked,
      word_timestamps: $("#optWords").checked,
      batch_size: $("#optBatch").value,
    };
  }

  async function start() {
    if (!state.file) { toast(t("toast.cannotStart"), "err"); return; }
    const err = validateFile(state.file);
    if (err) { toast(t("err." + err), "err"); return; }

    const opts = readOptions();
    const fd = new FormData();
    fd.append("file", state.file);
    Object.entries(opts).forEach(([k, v]) => fd.append(k, String(v)));

    $("#startBtn").disabled = true;
    $("#stateEmpty").hidden = true;
    $("#stateError").hidden = true;
    $("#stateResult").hidden = true;
    $("#stateProgress").hidden = false;
    $("#studioSub").textContent = t("studio.processing");
    $("#progressPct").innerHTML = `0<small>%</small>`;
    $("#progressFill").style.width = "0%";
    $("#progressStatus").textContent = t("msg.queued");
    $("#progressMeta").innerHTML = "";
    $("#langBadge").hidden = true;
    setStepper("queued");
    state.finished = false;

    try {
      const res = await fetch(API_BASE + "/api/jobs", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showError(data.error || "unknown", data.detail || "");
        return;
      }
      state.jobId = data.id;
      listen(data.id);
    } catch (e) {
      showError("network", String(e));
    }
  }

  function listen(id) {
    if (state.es) state.es.close();
    const es = new EventSource(`${API_BASE}/api/jobs/${id}/stream`);
    state.es = es;

    es.onmessage = (ev) => {
      let snap;
      try { snap = JSON.parse(ev.data); } catch (e) { return; }
      if (snap.status === "removed") { es.close(); return; }

      setProgress(snap);

      if (snap.status === "done") {
        state.finished = true;
        es.close(); state.es = null;
        finalize(id);
      } else if (snap.status === "error") {
        state.finished = true;
        es.close(); state.es = null;
        showError(snap.error_code || "unknown", snap.error_detail || "");
      } else if (snap.status === "canceled") {
        state.finished = true;
        es.close(); state.es = null;
        $("#studioSub").textContent = t("studio.canceled");
        toast(t("toast.canceled"), "info");
        showEmptyState("idle");
        $("#startBtn").disabled = !state.file;
      }
    };
    es.onerror = () => { /* stream closed after completion — ignore */ };
  }

  async function finalize(id) {
    try {
      const res = await fetch(API_BASE + `/api/jobs/${id}`);
      const data = await res.json();
      state.result = data;

      if (!data.has_speech || !data.text) {
        $("#studioSub").textContent = t("studio.done");
        showEmptyState("noSpeech");
        $("#startBtn").disabled = false;
        if (data.detected_language) {
          const b = $("#langBadge");
          b.hidden = false;
          b.textContent = data.detected_language.toUpperCase();
        }
        return;
      }
      renderResult(data);
      toast(t("toast.ready"), "ok");
    } catch (e) {
      showError("network", String(e));
    } finally {
      $("#startBtn").disabled = !state.file;
    }
  }

  function renderResult(res) {
    $("#stateEmpty").hidden = true;
    $("#stateProgress").hidden = true;
    $("#stateError").hidden = true;
    $("#stateResult").hidden = false;
    $("#studioSub").textContent = t("studio.done");

    if (res.detected_language) {
      const b = $("#langBadge");
      b.hidden = false;
      b.textContent = res.detected_language.toUpperCase();
    }

    const s = res.stats || {};
    const chips = [];
    if (s.words) chips.push(metaChip(t("stat.words"), s.words));
    if (s.characters) chips.push(metaChip(t("stat.chars"), s.characters));
    if (res.duration) chips.push(metaChip(t("stat.duration"), formatTime(res.duration)));
    if (s.segments) chips.push(metaChip(t("stat.segments"), s.segments));
    if (s.speed) chips.push(metaChip(t("stat.speed"), `${s.speed}${t("stat.rtf")}`));
    $("#resultStats").innerHTML = chips.join("");

    $("#transcriptText").textContent = res.text || "";
    renderTimeline(res.segments || []);
  }

  function renderTimeline(segments) {
    const box = $("#transcriptTimeline");
    box.innerHTML = "";
    const totalWords = segments.reduce((n, s) => n + ((s.words && s.words.length) || 0), 0);
    const useWords = totalWords > 0 && totalWords < 4000;

    segments.forEach((seg) => {
      const row = document.createElement("div");
      row.className = "timeline__row";

      const time = document.createElement("div");
      time.className = "timeline__time";
      time.textContent = `${formatTime(seg.start)} → ${formatTime(seg.end)}`;

      const text = document.createElement("div");
      text.className = "timeline__text";
      if (useWords && seg.words && seg.words.length) {
        seg.words.forEach((w) => {
          const span = document.createElement("span");
          span.className = "w";
          span.textContent = w.text + " ";
          span.title = `${formatTime(w.start)} → ${formatTime(w.end)}`;
          text.appendChild(span);
        });
      } else {
        text.textContent = seg.text;
      }

      row.appendChild(time);
      row.appendChild(text);
      box.appendChild(row);
    });
  }

  function showError(code, detail) {
    state.finished = true;
    showState("error");
    $("#studioSub").textContent = t("studio.error");
    const known = I18N[state.lang][`err.${code}`] || I18N.en[`err.${code}`];
    $("#errorMessage").textContent = known || t("err.unknown");
    const details = $("#errorDetails");
    if (detail && !known) {
      details.hidden = false;
      $("#errorDetail").textContent = detail;
    } else if (detail) {
      details.hidden = false;
      $("#errorDetail").textContent = `${code}: ${detail}`;
    } else {
      details.hidden = true;
    }
    $("#startBtn").disabled = !state.file;
  }

  /* --------------------------------------------------------------------- *
   *  Results actions
   * --------------------------------------------------------------------- */
  async function copyText() {
    const text = (state.result && state.result.text) || "";
    if (!text) { toast(t("action.copyFail"), "err"); return; }
    try {
      await navigator.clipboard.writeText(text);
      toast(t("action.copied"), "ok");
    } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); toast(t("action.copied"), "ok"); }
      catch (e2) { toast(t("action.copyFail"), "err"); }
      ta.remove();
    }
  }

  function download(format) {
    if (!state.jobId) return;
    const a = document.createElement("a");
    a.href = `${API_BASE}/api/jobs/${state.jobId}/download?format=${format}`;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function cancel() {
    if (!state.jobId) return;
    try { await fetch(API_BASE + `/api/jobs/${state.jobId}`, { method: "DELETE" }); } catch (e) { /* ignore */ }
    if (state.es) { state.es.close(); state.es = null; }
    $("#studioSub").textContent = t("studio.canceled");
    toast(t("toast.canceled"), "info");
    showEmptyState("idle");
    $("#startBtn").disabled = !state.file;
  }

  function newFile() {
    clearFile();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /* --------------------------------------------------------------------- *
   *  Tabs, menu, modal
   * --------------------------------------------------------------------- */
  function initTabs() {
    $$(".tab").forEach((tab) => tab.addEventListener("click", () => {
      $$(".tab").forEach((x) => x.classList.toggle("is-active", x === tab));
      const name = tab.dataset.tab;
      $("#paneText").hidden = name !== "text";
      $("#paneTimeline").hidden = name !== "timeline";
    }));
  }

  function initMenu() {
    const menu = $("#downloadMenu");
    const btn = $("#downloadBtn");
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = menu.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", String(open));
    });
    $$(".menu__item").forEach((item) => item.addEventListener("click", () => {
      download(item.dataset.format);
      menu.classList.remove("is-open");
      btn.setAttribute("aria-expanded", "false");
    }));
    document.addEventListener("click", () => {
      menu.classList.remove("is-open");
      btn.setAttribute("aria-expanded", "false");
    });
  }

  function initModal() {
    const modal = $("#helpModal");
    const open = () => { modal.hidden = false; document.body.style.overflow = "hidden"; };
    const close = () => { modal.hidden = true; document.body.style.overflow = ""; };
    $("#helpBtn").addEventListener("click", open);
    $$("#helpModal [data-close]").forEach((el) => el.addEventListener("click", close));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !modal.hidden) close();
    });
  }

  /* --------------------------------------------------------------------- *
   *  Misc
   * --------------------------------------------------------------------- */
  function escapeHtml(str) {
    return str.replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (state.peaks && !$("#waveform").hidden) drawPeaks($("#waveCanvas"), state.peaks);
    }, 200);
  });

  /* --------------------------------------------------------------------- *
   *  Boot
   * --------------------------------------------------------------------- */
  function boot() {
    initTheme();
    initLang();
    initDropzone();
    initTabs();
    initMenu();
    initModal();

    $("#startBtn").addEventListener("click", start);
    $("#cancelBtn").addEventListener("click", cancel);
    $("#retryBtn").addEventListener("click", start);
    $("#copyBtn").addEventListener("click", copyText);
    $("#newBtn").addEventListener("click", newFile);

    applyI18n();
    fetchHealth();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
