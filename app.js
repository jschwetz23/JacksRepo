// StudyFlow — web version. Pure HTML/CSS/JS so it runs on GitHub Pages.
// Data lives in this browser's localStorage (replaces the desktop app's SQLite file).

import {
  AttentionTracker, listCameras, FOCUSED, DISTRACTED, AWAY, OFF, STATE_LABELS,
} from "./camera.js";

// ============================================================ constants
const COLORS = {
  accent: "#7c6cff", success: "#34d399", warning: "#fbbf24", danger: "#f87171",
  break: "#38bdf8", text: "#e7e9f0", muted: "#8a91a8", faint: "#5b6178", border: "#262c3d",
};
const FOCUS = "focus", SHORT_BREAK = "short_break", LONG_BREAK = "long_break";
const PHASE_LABELS = { [FOCUS]: "Focus", [SHORT_BREAK]: "Short break", [LONG_BREAK]: "Long break" };
const PHASE_COLORS = { [FOCUS]: COLORS.accent, [SHORT_BREAK]: COLORS.break, [LONG_BREAK]: COLORS.success };
const STATE_COLORS = { [FOCUSED]: COLORS.success, [DISTRACTED]: COLORS.warning, [AWAY]: COLORS.danger, [OFF]: COLORS.faint };
const PRIORITIES = ["Low", "Medium", "High"];
const PRIORITY_COLORS = [COLORS.muted, COLORS.warning, COLORS.danger];
const LIVE_BUCKET_SEC = 5;
const MIN_SESSION_SEC = 60;
const STORAGE_KEY = "studyflow:v1";

const DEFAULT_SETTINGS = {
  focus_min: 25,
  short_break_min: 5,
  long_break_min: 15,
  long_every: 4,
  auto_start_next: false,
  camera_id: "",
  sensitivity: 2,
  distraction_alert: true,
  alert_after_sec: 20,
  auto_pause_away: false,
  away_pause_sec: 60,
  daily_goal_min: 120,
};

// ============================================================ helpers
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function fmtDuration(seconds) {
  seconds = Math.floor(seconds);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}
function fmtClock(seconds) {
  seconds = Math.max(0, Math.floor(seconds));
  const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
  const mm = String(m).padStart(2, "0"), ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}
// local-time YYYY-MM-DD
function dayKey(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function parseDay(key) {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function addDays(date, n) {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}
function daysUntil(key) {
  return Math.round((parseDay(key) - parseDay(dayKey())) / 86400000);
}
function setChip(el, text, color) {
  el.textContent = text;
  el.style.setProperty("--c", color);
}
function rateColor(pct) {
  return pct >= 75 ? COLORS.success : pct >= 50 ? COLORS.warning : COLORS.danger;
}

// ============================================================ storage
const store = {
  data: null,

  load() {
    let raw = null;
    try { raw = JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { /* ignore */ }
    this.data = {
      nextId: raw?.nextId ?? 1,
      tasks: Array.isArray(raw?.tasks) ? raw.tasks : [],
      sessions: Array.isArray(raw?.sessions) ? raw.sessions : [],
      settings: { ...DEFAULT_SETTINGS, ...(raw?.settings || {}) },
    };
  },
  save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.data));
    } catch (err) {
      console.error(err);
      alert("Couldn't save — your browser storage may be full or disabled.");
    }
  },

  get settings() { return this.data.settings; },
  saveSettings(values) { Object.assign(this.data.settings, values); this.save(); },

  // ---- tasks
  task(id) { return this.data.tasks.find((t) => t.id === id) || null; },
  addTask(values) {
    const t = { id: this.data.nextId++, done: false, created: Date.now(), ...values };
    this.data.tasks.push(t);
    this.save();
    return t.id;
  },
  updateTask(id, values) { Object.assign(this.task(id), values); this.save(); },
  setDone(id, done) { this.task(id).done = done; this.save(); },
  deleteTask(id) { this.data.tasks = this.data.tasks.filter((t) => t.id !== id); this.save(); },
  studiedFor(id) {
    return this.data.sessions.reduce((a, s) => a + (s.taskId === id ? s.studied : 0), 0);
  },
  tasks(includeDone = true) {
    return this.data.tasks
      .filter((t) => includeDone || !t.done)
      .sort((a, b) => (a.done - b.done) || a.due.localeCompare(b.due) || (b.priority - a.priority));
  },
  subjects() {
    return [...new Set(this.data.tasks.map((t) => t.subject).filter(Boolean))].sort();
  },

  // ---- sessions
  addSession(s) { this.data.sessions.push(s); this.save(); },
  recentSessions(limit = 20) {
    return [...this.data.sessions].sort((a, b) => b.started - a.started).slice(0, limit);
  },
  studiedOn(key) {
    return this.data.sessions.reduce((a, s) => a + (dayKey(new Date(s.started)) === key ? s.studied : 0), 0);
  },
  dailyTotals(days = 7) {
    const start = addDays(parseDay(dayKey()), -(days - 1));
    const out = [];
    for (let i = 0; i < days; i++) {
      const d = addDays(start, i);
      out.push([d, this.studiedOn(dayKey(d))]);
    }
    return out;
  },
  since(days) {
    const cutoff = addDays(parseDay(dayKey()), -(days - 1)).getTime();
    return this.data.sessions.filter((s) => s.started >= cutoff);
  },
  subjectTotals(days = 30) {
    const totals = {};
    for (const s of this.since(days)) {
      const subject = this.task(s.taskId)?.subject || s.subject || "Unassigned";
      totals[subject] = (totals[subject] || 0) + s.studied;
    }
    return Object.entries(totals).sort((a, b) => b[1] - a[1]).slice(0, 6);
  },
  focusRate(days = 7) {
    let cam = 0, foc = 0;
    for (const s of this.since(days)) { cam += s.camera; foc += s.focused; }
    return cam ? foc / cam : null;
  },
  streak() {
    const days = new Set(this.data.sessions.filter((s) => s.studied > 0).map((s) => dayKey(new Date(s.started))));
    let d = parseDay(dayKey());
    if (!days.has(dayKey(d))) d = addDays(d, -1); // streak survives until today is over
    let n = 0;
    while (days.has(dayKey(d))) { n++; d = addDays(d, -1); }
    return n;
  },
};

// ============================================================ sound
let audioCtx = null;
function unlockAudio() {
  if (!audioCtx) {
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch { /* no audio */ }
  }
  audioCtx?.resume?.();
}
const SOUNDS = {
  complete: [[784, 0], [1047, 0.16]],
  break_over: [[523, 0], [659, 0.14], [784, 0.28]],
  alert: [[880, 0]],
  paused: [[220, 0], [196, 0.2]],
};
function playSound(name) {
  if (!audioCtx) return;
  const now = audioCtx.currentTime;
  for (const [freq, at] of SOUNDS[name] || []) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, now + at);
    gain.gain.exponentialRampToValueAtTime(0.25, now + at + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + at + 0.5);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(now + at);
    osc.stop(now + at + 0.55);
  }
}

// ============================================================ pomodoro timer
class PomodoroTimer {
  constructor(settings, handlers) {
    this.settings = { ...settings };
    this.h = handlers; // ticked, progressed, phaseChanged, runningChanged, phaseCompleted
    this.phase = FOCUS;
    this.completedFocus = 0;
    this.total = this.durationFor(FOCUS);
    this.remaining = this.total;
    this.running = false;
    this._last = 0;
    this._interval = null;
  }
  durationFor(phase) {
    const key = { [FOCUS]: "focus_min", [SHORT_BREAK]: "short_break_min", [LONG_BREAK]: "long_break_min" }[phase];
    return Number(this.settings[key]) * 60;
  }
  get longEvery() { return Math.max(1, Number(this.settings.long_every)); }
  configure(settings) {
    this.settings = { ...settings };
    if (!this.running && this.remaining >= this.total) {
      this.total = this.durationFor(this.phase);
      this.remaining = this.total;
      this._emitTick();
    }
  }
  start() {
    if (this.running) return;
    this._last = performance.now();
    this._interval = setInterval(() => this._onTick(), 200);
    this.running = true;
    this.h.runningChanged(true);
  }
  pause() {
    if (!this.running) return;
    this._onTick(false);
    clearInterval(this._interval);
    this.running = false;
    this.h.runningChanged(false);
  }
  toggle() { this.running ? this.pause() : this.start(); }
  reset() { this.pause(); this.remaining = this.total; this._emitTick(); }
  skip() { this._advance(false); }
  setPhase(phase) {
    this.pause();
    this.phase = phase;
    this.total = this.durationFor(phase);
    this.remaining = this.total;
    this.h.phaseChanged(phase);
    this._emitTick();
  }
  _onTick(checkDone = true) {
    if (!this.running) return;
    const now = performance.now();
    const dt = Math.min((now - this._last) / 1000, this.remaining);
    this._last = now;
    this.remaining -= dt;
    this.h.progressed(this.phase, dt);
    this._emitTick();
    if (checkDone && this.running && this.remaining <= 0.05) {
      this.h.phaseCompleted(this.phase);
      this._advance(true);
    }
  }
  _advance(natural) {
    const finished = this.phase;
    let next = FOCUS;
    if (finished === FOCUS) {
      if (natural) this.completedFocus++;
      next = natural && this.completedFocus % this.longEvery === 0 ? LONG_BREAK : SHORT_BREAK;
    }
    this.setPhase(next);
    if (natural && this.settings.auto_start_next) this.start();
  }
  _emitTick() { this.h.ticked(Math.ceil(Math.max(0, this.remaining)), this.total); }
}

// ============================================================ charts (SVG)
function emptyChart(el, text) {
  el.innerHTML = `<div class="chart-empty">${esc(text)}</div>`;
}

function lineChart(el, values, { color = COLORS.success, axis = true, emptyText = "", maxPoints = 60 } = {}) {
  values = values.slice(-maxPoints);
  if (values.length < 2) return emptyChart(el, emptyText);
  const W = el.clientWidth || 400, H = el.clientHeight || 120;
  const padL = axis ? 34 : 2, padR = 6, padT = 8, padB = axis ? 8 : 4;
  const iw = W - padL - padR, ih = H - padT - padB;
  const x = (i) => padL + (i / (values.length - 1)) * iw;
  const y = (v) => padT + (1 - Math.max(0, Math.min(100, v)) / 100) * ih;
  const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  const id = `g${Math.random().toString(36).slice(2, 8)}`;
  let grid = "";
  if (axis) {
    for (const g of [0, 50, 100]) {
      grid += `<line x1="${padL}" x2="${W - padR}" y1="${y(g)}" y2="${y(g)}" stroke="${COLORS.border}" stroke-dasharray="3 4"/>`;
      grid += `<text x="${padL - 8}" y="${y(g) + 4}" text-anchor="end">${g}%</text>`;
    }
  }
  const last = values[values.length - 1];
  el.innerHTML = `
    <svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${color}" stop-opacity="0.35"/>
        <stop offset="1" stop-color="${color}" stop-opacity="0"/>
      </linearGradient></defs>
      ${grid}
      <polygon points="${x(0)},${padT + ih} ${pts.join(" ")} ${x(values.length - 1)},${padT + ih}" fill="url(#${id})"/>
      <polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="${x(values.length - 1)}" cy="${y(last)}" r="3.5" fill="${color}"/>
    </svg>`;
}

function barChart(el, values, labels, goal) {
  const W = el.clientWidth || 600, H = el.clientHeight || 220;
  const padL = 40, padR = 8, padT = 10, padB = 24;
  const iw = W - padL - padR, ih = H - padT - padB;
  const max = Math.max(goal || 0, ...values, 30) * 1.1;
  const y = (v) => padT + (1 - v / max) * ih;
  const slot = iw / values.length;
  const bw = Math.min(46, slot * 0.6);
  let out = "";
  const step = max > 240 ? 120 : max > 120 ? 60 : 30;
  for (let g = 0; g <= max; g += step) {
    out += `<line x1="${padL}" x2="${W - padR}" y1="${y(g)}" y2="${y(g)}" stroke="${COLORS.border}"/>`;
    out += `<text x="${padL - 8}" y="${y(g) + 4}" text-anchor="end">${g >= 60 ? `${g / 60}h` : `${g}m`}</text>`;
  }
  values.forEach((v, i) => {
    const cx = padL + slot * i + slot / 2;
    const top = y(v);
    const reached = goal && v >= goal;
    const fill = v > 0 ? (reached ? COLORS.success : COLORS.accent) : COLORS.border;
    const h = Math.max(v > 0 ? 3 : 2, padT + ih - top);
    out += `<rect x="${cx - bw / 2}" y="${padT + ih - h}" width="${bw}" height="${h}" rx="5" fill="${fill}"><title>${Math.round(v)} min</title></rect>`;
    if (v > 0) out += `<text x="${cx}" y="${padT + ih - h - 6}" text-anchor="middle" style="fill:${COLORS.muted}">${Math.round(v)}m</text>`;
    out += `<text x="${cx}" y="${H - 6}" text-anchor="middle">${esc(labels[i])}</text>`;
  });
  if (goal) {
    out += `<line x1="${padL}" x2="${W - padR}" y1="${y(goal)}" y2="${y(goal)}" stroke="${COLORS.warning}" stroke-dasharray="6 5" stroke-width="1.5"/>`;
    out += `<text x="${W - padR}" y="${y(goal) - 6}" text-anchor="end" style="fill:${COLORS.warning}">goal</text>`;
  }
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}">${out}</svg>`;
}

function hbars(el, rows) {
  if (!rows.length) return emptyChart(el, "No study time logged yet");
  const max = Math.max(...rows.map((r) => r[1]), 1);
  const palette = [COLORS.accent, COLORS.break, COLORS.success, COLORS.warning, COLORS.danger, COLORS.muted];
  el.innerHTML = rows.map(([name, sec], i) => `
    <div>
      <div class="hbar-top"><span>${esc(name)}</span><span>${fmtDuration(sec)}</span></div>
      <div class="bar"><div class="bar-fill" style="width:${(100 * sec) / max}%;background:${palette[i % palette.length]}"></div></div>
    </div>`).join("");
}

// ============================================================ focus page
const focus = {
  init() {
    this.settings = { ...store.settings };
    this.camState = OFF;
    this.session = null;
    this.completedNaturally = false;
    this.bucket = [0, 0];
    this.liveData = [];
    this.notFocusedSince = null;
    this.awaySince = null;
    this.alerted = false;

    this.timer = new PomodoroTimer(this.settings, {
      ticked: (r, t) => this.onTick(r, t),
      progressed: (p, dt) => this.onProgress(p, dt),
      phaseChanged: (p) => this.onPhaseChanged(p),
      runningChanged: (r) => this.onRunningChanged(r),
      phaseCompleted: (p) => this.onPhaseCompleted(p),
    });

    this.tracker = new AttentionTracker($("#video"), $("#overlay"), {
      onState: (s) => { if (this.tracker.active) this.setCamState(s); },
      onError: (msg) => this.stopCamera(msg),
      onReady: () => { $("#camera-msg").hidden = true; refreshCameraList(); },
    });
    this.tracker.sensitivity = Number(this.settings.sensitivity);

    $("#today-date").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
    $("#play-btn").onclick = () => { unlockAudio(); this.timer.toggle(); };
    $("#reset-btn").onclick = () => this.reset();
    $("#skip-btn").onclick = () => this.timer.skip();
    $("#cam-btn").onclick = () => { unlockAudio(); this.toggleCamera(); };
    $$("#phase-pills .pill").forEach((b) => {
      b.onclick = () => { if (b.dataset.phase !== this.timer.phase) this.timer.setPhase(b.dataset.phase); };
    });
    $("#task-select").onchange = () => this.finalizeSession(false);

    const ring = $("#ring-bar");
    this.circ = 2 * Math.PI * Number(ring.getAttribute("r"));
    ring.style.strokeDasharray = this.circ;

    this.refreshTasks();
    this.setCamState(OFF, true);
    this.onPhaseChanged(this.timer.phase);
    this.updateToday();
    this.updateRate();
    lineChart($("#live-chart"), [], { axis: false, emptyText: "Live focus graph appears here" });
  },

  // ---- public
  refreshTasks() {
    const sel = $("#task-select");
    const current = sel.value;
    const opts = [`<option value="">General study (no specific item)</option>`];
    for (const t of store.tasks(false)) {
      const due = parseDay(t.due).toLocaleDateString(undefined, { month: "short", day: "numeric" });
      const subject = t.subject ? ` · ${t.subject}` : "";
      opts.push(`<option value="${t.id}">${esc(t.title + subject)}  (due ${due})</option>`);
    }
    sel.innerHTML = opts.join("");
    sel.value = [...sel.options].some((o) => o.value === current) ? current : "";
  },
  selectTask(id) {
    this.refreshTasks();
    const sel = $("#task-select");
    if (sel.value !== String(id)) {
      this.finalizeSession(false);
      sel.value = String(id);
    }
  },
  currentTaskId() {
    const v = $("#task-select").value;
    return v ? Number(v) : null;
  },
  applySettings(settings) {
    const old = this.settings;
    this.settings = { ...settings };
    this.timer.configure(this.settings);
    this.tracker.sensitivity = Number(this.settings.sensitivity);
    if (this.tracker.active && old.camera_id !== this.settings.camera_id) {
      this.stopCamera();
      this.startCamera();
    }
    this.updateToday();
  },
  shutdown() {
    this.timer.pause();
    this.finalizeSession(false);
  },

  // ---- camera
  toggleCamera() { this.tracker.active ? this.stopCamera() : this.startCamera(); },
  startCamera() {
    const msg = $("#camera-msg");
    msg.hidden = false;
    msg.innerHTML = "Starting camera…<br><br><span class='faint'>The first time, the face-tracking model takes a few seconds to download.</span>";
    $("#cam-btn").textContent = "Turn off camera";
    this.tracker.start(this.settings.camera_id || undefined);
  },
  stopCamera(message = "") {
    this.tracker.stop();
    $("#cam-btn").textContent = "Turn on camera";
    const msg = $("#camera-msg");
    msg.hidden = false;
    msg.innerHTML = message ? esc(message) : "Camera is off<br><br>Turn it on to measure your active study rate";
    this.setCamState(OFF);
  },
  setCamState(state, force = false) {
    const now = performance.now();
    if (state !== this.camState || force) setChip($("#state-chip"), `● ${STATE_LABELS[state]}`, STATE_COLORS[state]);
    this.camState = state;
    if (state === FOCUSED || state === OFF) {
      this.notFocusedSince = null;
      this.awaySince = null;
      if (this.alerted) { this.alerted = false; this.hideBanner(); }
      return;
    }
    if (this.notFocusedSince === null) this.notFocusedSince = now;
    if (state === AWAY) { if (this.awaySince === null) this.awaySince = now; }
    else this.awaySince = null;
  },

  // ---- timer
  reset() {
    if (this.timer.phase === FOCUS) this.finalizeSession(false);
    this.timer.reset();
  },
  onRunningChanged(running) {
    if (running) {
      $("#play-btn").textContent = "Pause";
      this.hideBanner();
      this.alerted = false;
      const now = performance.now();
      if (this.notFocusedSince !== null) this.notFocusedSince = now;
      if (this.awaySince !== null) this.awaySince = now;
    } else {
      $("#play-btn").textContent = this.timer.remaining < this.timer.total ? "Resume" : "Start";
      document.title = "StudyFlow";
    }
  },
  onTick(remaining, total) {
    const phase = this.timer.phase;
    const every = this.timer.longEvery;
    const foot = phase === FOCUS ? `Round ${(this.timer.completedFocus % every) + 1} of ${every}`
      : phase === SHORT_BREAK ? "Stretch · hydrate · rest your eyes" : "Long break — you earned it";
    const progress = total ? 1 - remaining / total : 0;
    $("#ring-time").textContent = fmtClock(remaining);
    $("#ring-phase").textContent = PHASE_LABELS[phase];
    $("#ring-foot").textContent = foot;
    const ring = $("#ring-bar");
    ring.style.stroke = PHASE_COLORS[phase];
    ring.style.strokeDashoffset = this.circ * (1 - progress);
    if (this.timer.running) document.title = `${fmtClock(remaining)} · ${PHASE_LABELS[phase]}`;
  },
  onPhaseChanged(phase) {
    this.finalizeSession(this.completedNaturally);
    this.completedNaturally = false;
    $$("#phase-pills .pill").forEach((b) => b.classList.toggle("active", b.dataset.phase === phase));
    $("#play-btn").textContent = "Start";
  },
  onPhaseCompleted(phase) {
    if (phase === FOCUS) {
      this.completedNaturally = true;
      this.showBanner("Focus block complete — nice work. Time for a break.", COLORS.success);
      playSound("complete");
    } else {
      this.showBanner("Break's over. Ready for another focus block?", COLORS.break);
      playSound("break_over");
    }
  },
  onProgress(phase, dt) {
    if (phase !== FOCUS || dt <= 0) return;
    if (!this.session) {
      const id = this.currentTaskId();
      const task = id ? store.task(id) : null;
      this.session = {
        taskId: id, taskTitle: task?.title || "", subject: task?.subject || "",
        started: Date.now() - dt * 1000, planned: this.timer.total,
        studied: 0, camera: 0, focused: 0,
      };
      this.liveData = [];
      lineChart($("#live-chart"), [], { axis: false, emptyText: "Live focus graph appears here" });
    }
    const s = this.session;
    s.studied += dt;
    if (this.camState !== OFF) {
      s.camera += dt;
      this.bucket[0] += dt;
      if (this.camState === FOCUSED) { s.focused += dt; this.bucket[1] += dt; }
    }
    if (this.bucket[0] >= LIVE_BUCKET_SEC) {
      this.liveData.push((100 * this.bucket[1]) / this.bucket[0]);
      this.bucket = [0, 0];
      lineChart($("#live-chart"), this.liveData, { axis: false, emptyText: "Live focus graph appears here" });
    }
    this.updateRate();
    this.checkDistraction();
  },
  checkDistraction() {
    const now = performance.now();
    const st = this.settings;
    if (st.auto_pause_away && this.awaySince !== null && (now - this.awaySince) / 1000 >= st.away_pause_sec) {
      this.timer.pause();
      this.alerted = true;
      this.showBanner("Timer paused — looks like you stepped away. Press Resume when you're back.", COLORS.danger);
      playSound("paused");
      return;
    }
    if (st.distraction_alert && !this.alerted && this.notFocusedSince !== null
        && (now - this.notFocusedSince) / 1000 >= st.alert_after_sec) {
      this.alerted = true;
      const what = this.camState === AWAY ? "away from your desk" : "distracted";
      this.showBanner(`You've seemed ${what} for a bit — eyes back on the material 👀`, COLORS.warning);
      playSound("alert");
    }
  },
  updateRate() {
    const s = this.session;
    const val = $("#rate-value"), detail = $("#rate-detail");
    if (!s || s.camera < 1) {
      val.textContent = "—";
      val.style.color = "";
      detail.textContent = s && this.camState === OFF
        ? `${fmtDuration(s.studied)} studied · turn on the camera to track focus`
        : "Start a focus block with the camera on";
      return;
    }
    const pct = (100 * s.focused) / s.camera;
    val.textContent = `${Math.round(pct)}%`;
    val.style.color = rateColor(pct);
    detail.textContent = `Focused ${fmtClock(s.focused)} of ${fmtClock(s.camera)} tracked`;
  },
  showBanner(text, color) {
    const b = $("#banner");
    b.textContent = text;
    b.style.setProperty("--c", color);
    b.hidden = false;
  },
  hideBanner() { $("#banner").hidden = true; },
  finalizeSession(completed) {
    const s = this.session;
    this.session = null;
    this.bucket = [0, 0];
    if (!s) return;
    this.updateRate();
    // short partial sessions are noise; a fully completed block always counts
    if (!s || s.studied < 1 || (s.studied < MIN_SESSION_SEC && !completed)) return;
    store.addSession({
      taskId: s.taskId, taskTitle: s.taskTitle, subject: s.subject,
      started: Math.round(s.started), ended: Date.now(), planned: s.planned,
      studied: Math.round(s.studied), camera: Math.round(s.camera), focused: Math.round(s.focused),
      completed: Boolean(completed),
    });
    this.updateToday();
    this.updateRate();
    planner.refresh();
    refreshUpcoming();
  },
  updateToday() {
    const studied = store.studiedOn(dayKey());
    const goal = Number(this.settings.daily_goal_min) * 60;
    $("#today-label").textContent = `Today: ${fmtDuration(studied)} studied`;
    $("#goal-label").textContent = `DAILY GOAL ${fmtDuration(goal)}`;
    const fill = $("#goal-fill");
    fill.style.width = `${Math.min(100, (100 * studied) / Math.max(1, goal))}%`;
    fill.classList.toggle("done", studied >= goal);
  },
};

// ============================================================ planner page
const planner = {
  editingId: null,
  filter: "Open",

  init() {
    $("#task-form").onsubmit = (e) => { e.preventDefault(); this.save(); };
    $("#f-cancel").onclick = () => this.clearForm();
    $("#search").oninput = () => this.refresh();
    $$("#filter-pills .pill").forEach((b) => {
      b.onclick = () => { this.filter = b.dataset.filter; this.refresh(); };
    });
    $("#task-list").addEventListener("click", (e) => this.onListClick(e));
    $("#task-list").addEventListener("change", (e) => {
      if (e.target.matches("input[type=checkbox]")) {
        store.setDone(Number(e.target.dataset.id), e.target.checked);
        tasksChanged();
      }
    });
    this.clearForm();
    this.refresh();
  },

  refresh() {
    const today = dayKey();
    const all = store.tasks(true);
    const open = all.filter((t) => !t.done);
    const overdue = open.filter((t) => t.due < today);
    const week = open.filter((t) => { const d = daysUntil(t.due); return d >= 0 && d <= 7; });
    setChip($("#chip-overdue"), `${overdue.length} overdue`, overdue.length ? COLORS.danger : COLORS.faint);
    setChip($("#chip-week"), `${week.length} due this week`, COLORS.warning);
    setChip($("#chip-open"), `${open.length} open`, COLORS.accent);
    $$("#filter-pills .pill").forEach((b) => b.classList.toggle("active", b.dataset.filter === this.filter));

    const q = $("#search").value.trim().toLowerCase();
    const keep = (t) => {
      if (q && !`${t.title} ${t.subject} ${t.notes}`.toLowerCase().includes(q)) return false;
      const d = daysUntil(t.due);
      return {
        "Open": !t.done,
        "This week": !t.done && d <= 7,
        "Overdue": !t.done && d < 0,
        "Done": t.done,
        "All": true,
      }[this.filter];
    };
    const rows = all.filter(keep);

    $("#task-list").innerHTML = rows.map((t) => this.rowHtml(t)).join("");
    const empty = $("#task-empty");
    empty.hidden = rows.length > 0;
    empty.textContent = all.length ? "No items match this filter." : "Nothing here yet — add what you need to study with the form.";
    $("#subject-list").innerHTML = store.subjects().map((s) => `<option value="${esc(s)}">`).join("");
  },

  rowHtml(t) {
    const [dueText, dueColor] = dueLabel(t.due, t.done);
    const studiedH = store.studiedFor(t.id) / 3600;
    const pct = t.done ? 100 : Math.min(100, (100 * studiedH) / Math.max(t.est, 0.01));
    return `
      <div class="task${t.done ? " done" : ""}">
        <input type="checkbox" data-id="${t.id}" ${t.done ? "checked" : ""} aria-label="Mark done">
        <div>
          <div class="task-title">${esc(t.title)}</div>
          <div class="task-meta">
            <span>${esc(t.subject || "—")}</span>
            <span style="color:${PRIORITY_COLORS[t.priority]}">● ${PRIORITIES[t.priority]}</span>
          </div>
          ${t.notes ? `<div class="task-notes">${esc(t.notes)}</div>` : ""}
        </div>
        <div class="task-due" style="color:${dueColor}">${esc(dueText)}</div>
        <div class="task-prog">
          <div class="bar"><div class="bar-fill${t.done ? " done" : ""}" style="width:${pct}%"></div></div>
          <span class="faint">${studiedH.toFixed(1)} / ${+t.est} h studied</span>
        </div>
        <div class="task-actions">
          ${t.done ? "" : `<button class="small primary" data-act="study" data-id="${t.id}">▶ Study</button>`}
          <button class="small" data-act="edit" data-id="${t.id}">Edit</button>
          <button class="small danger" data-act="delete" data-id="${t.id}">Delete</button>
        </div>
      </div>`;
  },

  onListClick(e) {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const task = store.task(id);
    if (!task) return;
    if (btn.dataset.act === "study") {
      focus.selectTask(id);
      location.hash = "#focus";
    } else if (btn.dataset.act === "edit") {
      this.edit(task);
    } else if (btn.dataset.act === "delete") {
      if (confirm(`Delete “${task.title}”? Study time you logged stays in your insights.`)) {
        store.deleteTask(id);
        if (this.editingId === id) this.clearForm();
        tasksChanged();
      }
    }
  },

  save() {
    const titleEl = $("#f-title");
    const title = titleEl.value.trim();
    if (!title) { titleEl.classList.add("invalid"); titleEl.focus(); return; }
    titleEl.classList.remove("invalid");
    const est = Math.min(500, Math.max(0.5, Number($("#f-est").value) || 1));
    const values = {
      title,
      subject: $("#f-subject").value.trim(),
      due: $("#f-due").value || dayKey(addDays(new Date(), 7)),
      priority: Number($("#f-priority").value),
      est,
      notes: $("#f-notes").value.trim(),
    };
    if (this.editingId === null) store.addTask(values);
    else store.updateTask(this.editingId, values);
    this.clearForm();
    tasksChanged();
  },

  clearForm() {
    this.editingId = null;
    $("#f-title").value = "";
    $("#f-title").classList.remove("invalid");
    $("#f-subject").value = "";
    $("#f-due").value = dayKey(addDays(new Date(), 7));
    $("#f-priority").value = "1";
    $("#f-est").value = "2";
    $("#f-notes").value = "";
    $("#f-save").textContent = "Add to planner";
    $("#f-cancel").hidden = true;
    $("#form-title").textContent = "Add a study item";
  },

  edit(t) {
    this.editingId = t.id;
    $("#f-title").value = t.title;
    $("#f-subject").value = t.subject;
    $("#f-due").value = t.due;
    $("#f-priority").value = String(t.priority);
    $("#f-est").value = String(t.est);
    $("#f-notes").value = t.notes;
    $("#f-save").textContent = "Save changes";
    $("#f-cancel").hidden = false;
    $("#form-title").textContent = "Edit study item";
    $("#task-form").scrollIntoView({ behavior: "smooth", block: "start" });
    $("#f-title").focus({ preventScroll: true });
  },
};

function dueLabel(key, done) {
  const days = daysUntil(key);
  const base = parseDay(key).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  if (done) return [base, COLORS.faint];
  if (days < 0) return [`${base} · ${-days}d late`, COLORS.danger];
  if (days === 0) return [`${base} · today`, COLORS.warning];
  if (days === 1) return [`${base} · tomorrow`, COLORS.warning];
  if (days <= 3) return [`${base} · in ${days}d`, COLORS.warning];
  return [`${base} · in ${days}d`, COLORS.text];
}

// ============================================================ insights page
const insights = {
  refresh() {
    const settings = store.settings;
    const todaySec = store.studiedOn(dayKey());
    const goal = Number(settings.daily_goal_min) * 60;
    $("#st-today").textContent = fmtDuration(todaySec);
    $("#st-today-sub").textContent = `${Math.min(100, Math.floor((100 * todaySec) / Math.max(goal, 1)))}% of daily goal`;

    const totals = store.dailyTotals(7);
    const weekSec = totals.reduce((a, [, s]) => a + s, 0);
    const active = totals.filter(([, s]) => s > 0).length;
    $("#st-week").textContent = fmtDuration(weekSec);
    $("#st-week-sub").textContent = `${active} of 7 days active`;

    const rate = store.focusRate(7);
    $("#st-rate").textContent = rate === null ? "—" : `${Math.round(rate * 100)}%`;
    $("#st-rate-sub").textContent = rate === null ? "Turn on the camera while studying" : "of tracked time, last 7 days";

    const streak = store.streak();
    $("#st-streak").textContent = `${streak} day${streak === 1 ? "" : "s"}`;
    $("#st-streak-sub").textContent = streak ? "Keep it going!" : "Study today to start one";

    const todayKey = dayKey();
    barChart(
      $("#week-chart"),
      totals.map(([, s]) => s / 60),
      totals.map(([d]) => (dayKey(d) === todayKey ? "Today" : d.toLocaleDateString(undefined, { weekday: "short" }))),
      goal / 60,
    );
    hbars($("#subject-bars"), store.subjectTotals(30));

    const sessions = store.recentSessions(30);
    const tracked = sessions.slice().reverse().filter((s) => s.camera > 0).slice(-15);
    lineChart($("#rate-chart"), tracked.map((s) => (100 * s.focused) / s.camera),
      { axis: true, emptyText: "Finish two sessions with the camera on" });

    const rows = sessions.slice(0, 12);
    const yesterday = dayKey(addDays(new Date(), -1));
    $("#sessions-body").innerHTML = rows.length ? rows.map((s) => {
      const d = new Date(s.started);
      const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
      const k = dayKey(d);
      const when = k === todayKey ? `Today ${time}` : k === yesterday ? `Yesterday ${time}`
        : `${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })} ${time}`;
      const title = store.task(s.taskId)?.title || s.taskTitle || "General study";
      let focusCell = `<span style="color:${COLORS.faint}">—</span>`;
      if (s.camera) {
        const pct = (100 * s.focused) / s.camera;
        focusCell = `<span style="color:${rateColor(pct)}">${Math.round(pct)}%</span>`;
      }
      return `<tr><td>${esc(when)}</td><td>${fmtDuration(s.studied)}${s.completed ? "" : ' <span class="faint">partial</span>'}</td><td>${esc(title)}</td><td>${focusCell}</td></tr>`;
    }).join("") : `<tr><td colspan="4" class="muted" style="padding:20px 6px">No sessions yet — sessions over a minute long show up here.</td></tr>`;
  },
};

// ============================================================ settings page
const settingsPage = {
  init() {
    const form = $("#settings-form");
    form.onsubmit = (e) => { e.preventDefault(); this.save(); };
    form.distraction_alert.onchange = () => this.syncEnabled();
    form.auto_pause_away.onchange = () => this.syncEnabled();
    $("#export-btn").onclick = exportData;
    $("#import-file").onchange = importData;
    $("#wipe-btn").onclick = wipeData;
    this.load();
  },
  load() {
    const form = $("#settings-form");
    const s = store.settings;
    for (const [k, v] of Object.entries(s)) {
      const el = form.elements[k];
      if (!el) continue;
      if (el.type === "checkbox") el.checked = Boolean(v);
      else el.value = String(v);
    }
    this.syncEnabled();
  },
  syncEnabled() {
    const form = $("#settings-form");
    form.alert_after_sec.disabled = !form.distraction_alert.checked;
    form.away_pause_sec.disabled = !form.auto_pause_away.checked;
  },
  save() {
    const form = $("#settings-form");
    const num = (name, lo, hi) => {
      const v = Math.round(Number(form.elements[name].value));
      return Math.min(hi, Math.max(lo, Number.isFinite(v) ? v : DEFAULT_SETTINGS[name]));
    };
    const values = {
      focus_min: num("focus_min", 1, 180),
      short_break_min: num("short_break_min", 1, 60),
      long_break_min: num("long_break_min", 1, 90),
      long_every: num("long_every", 1, 12),
      daily_goal_min: num("daily_goal_min", 10, 960),
      auto_start_next: form.auto_start_next.checked,
      camera_id: form.camera_id.value,
      sensitivity: Number(form.sensitivity.value),
      distraction_alert: form.distraction_alert.checked,
      alert_after_sec: num("alert_after_sec", 5, 600),
      auto_pause_away: form.auto_pause_away.checked,
      away_pause_sec: num("away_pause_sec", 10, 900),
    };
    store.saveSettings(values);
    focus.applySettings(store.settings);
    this.load();
    const lbl = $("#saved-label");
    lbl.textContent = "✓ Saved";
    setTimeout(() => { lbl.textContent = ""; }, 2000);
  },
};

async function refreshCameraList() {
  const sel = $("#camera-select");
  try {
    const cams = await listCameras();
    const current = store.settings.camera_id;
    sel.innerHTML = `<option value="">Default camera</option>` + cams.map((c, i) =>
      `<option value="${esc(c.deviceId)}">${esc(c.label || `Camera ${i + 1}`)}</option>`).join("");
    sel.value = [...sel.options].some((o) => o.value === current) ? current : "";
  } catch { /* leave default */ }
}

// ============================================================ backup
function exportData() {
  const blob = new Blob([JSON.stringify(store.data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `studyflow-backup-${dayKey()}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
async function importData(e) {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    if (!Array.isArray(data.tasks) || !Array.isArray(data.sessions)) throw new Error("bad file");
    if (!confirm("Replace everything in this browser with the backup?")) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    location.reload();
  } catch {
    alert("That file doesn't look like a StudyFlow backup.");
  }
}
function wipeData() {
  if (!confirm("Delete all tasks, sessions and settings in this browser? This can't be undone.")) return;
  focus.session = null;
  localStorage.removeItem(STORAGE_KEY);
  location.reload();
}

// ============================================================ app shell
function refreshUpcoming() {
  const tasks = store.tasks(false).slice(0, 4);
  const el = $("#upcoming");
  if (!tasks.length) { el.textContent = "Nothing due — add items in the Planner."; return; }
  el.innerHTML = tasks.map((t) => {
    const d = daysUntil(t.due);
    const [when, color] = d < 0 ? [`${-d}d late`, COLORS.danger]
      : d === 0 ? ["today", COLORS.warning]
      : [`in ${d}d`, d <= 3 ? COLORS.warning : COLORS.muted];
    return `<div class="up-item"><span class="t" title="${esc(t.title)}">${esc(t.title)}</span><span style="color:${color}">${when}</span></div>`;
  }).join("");
}

function tasksChanged() {
  planner.refresh();
  focus.refreshTasks();
  refreshUpcoming();
}

const PAGES = ["focus", "planner", "insights", "settings"];
function route() {
  const page = PAGES.includes(location.hash.slice(1)) ? location.hash.slice(1) : "focus";
  for (const p of PAGES) $(`#page-${p}`).hidden = p !== page;
  $$(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  if (page === "planner") planner.refresh();
  if (page === "insights") insights.refresh();
  if (page === "settings") { settingsPage.load(); refreshCameraList(); }
  window.scrollTo(0, 0);
}

store.load();
focus.init();
planner.init();
settingsPage.init();
refreshUpcoming();
window.addEventListener("hashchange", route);
route();

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (!$("#page-insights").hidden) insights.refresh();
    lineChart($("#live-chart"), focus.liveData, { axis: false, emptyText: "Live focus graph appears here" });
  }, 150);
});

// save a partial session if the tab is closed mid-block
window.addEventListener("pagehide", () => focus.shutdown());
