// Camera-based attention tracking, running entirely in the browser.
//
// Uses Google's MediaPipe Face Landmarker (loaded from a CDN) instead of the
// OpenCV Haar cascades the desktop version used. Per frame:
//
//   no face found                                  -> away
//   face turned well away, or eyes closed          -> distracted
//   face toward the screen with eyes open          -> focused
//
// Raw readings are smoothed over a 3-second window, like the desktop app.

const MP_VERSION = "0.10.14";
const MP_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VERSION}/vision_bundle.mjs`;
const WASM_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VERSION}/wasm`;
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

export const FOCUSED = "focused";
export const DISTRACTED = "distracted";
export const AWAY = "away";
export const OFF = "off";

export const STATE_LABELS = {
  [FOCUSED]: "Focused",
  [DISTRACTED]: "Distracted",
  [AWAY]: "Away",
  [OFF]: "Camera off",
};

// sensitivity -> max head turn (degrees), eye-closed score, share of focused frames required
const SENSITIVITY = {
  1: { maxAngle: 38, blink: 0.65, share: 0.35 },
  2: { maxAngle: 28, blink: 0.55, share: 0.5 },
  3: { maxAngle: 20, blink: 0.45, share: 0.65 },
};

const SMOOTHING_WINDOW_MS = 3000;
const DETECT_INTERVAL_MS = 90;
const BOX_COLORS = { [FOCUSED]: "#34d399", [DISTRACTED]: "#fbbf24", [AWAY]: "#f87171" };

let landmarkerPromise = null;

async function getLandmarker() {
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      const { FaceLandmarker, FilesetResolver } = await import(MP_URL);
      const fileset = await FilesetResolver.forVisionTasks(WASM_URL);
      const opts = (delegate) => ({
        baseOptions: { modelAssetPath: MODEL_URL, delegate },
        runningMode: "VIDEO",
        numFaces: 1,
        outputFaceBlendshapes: true,
        outputFacialTransformationMatrixes: true,
      });
      try {
        return await FaceLandmarker.createFromOptions(fileset, opts("GPU"));
      } catch {
        return await FaceLandmarker.createFromOptions(fileset, opts("CPU"));
      }
    })();
    landmarkerPromise.catch(() => { landmarkerPromise = null; });
  }
  return landmarkerPromise;
}

export class AttentionTracker {
  constructor(video, canvas, { onState, onError, onReady } = {}) {
    this.video = video;
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.onState = onState || (() => {});
    this.onError = onError || (() => {});
    this.onReady = onReady || (() => {});
    this.sensitivity = 2;
    this.stream = null;
    this.running = false;
    this.history = [];
    this._timer = null;
    this._lastTs = 0;
  }

  get active() { return this.running; }

  async start(deviceId) {
    if (this.running) return;
    this.running = true;
    this.history = [];
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser can't access a camera (the page must be opened over https).");
      }
      const video = deviceId ? { deviceId: { exact: deviceId } } : { facingMode: "user" };
      video.width = { ideal: 640 };
      video.height = { ideal: 480 };
      const [stream, landmarker] = await Promise.all([
        navigator.mediaDevices.getUserMedia({ video, audio: false }),
        getLandmarker(),
      ]);
      if (!this.running) { stream.getTracks().forEach((t) => t.stop()); return; }
      this.stream = stream;
      this.landmarker = landmarker;
      this.video.srcObject = stream;
      await this.video.play();
      this.onReady();
      this._loop();
    } catch (err) {
      this.stop();
      this.onError(friendlyError(err));
    }
  }

  stop() {
    this.running = false;
    clearTimeout(this._timer);
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.video.srcObject = null;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  _loop() {
    if (!this.running) return;
    try {
      this._detect();
    } catch (err) {
      console.error(err);
    }
    this._timer = setTimeout(() => this._loop(), DETECT_INTERVAL_MS);
  }

  _detect() {
    const v = this.video;
    if (v.readyState < 2 || !v.videoWidth) return;
    if (this.canvas.width !== v.videoWidth) {
      this.canvas.width = v.videoWidth;
      this.canvas.height = v.videoHeight;
    }
    let ts = performance.now();
    if (ts <= this._lastTs) ts = this._lastTs + 1;
    this._lastTs = ts;

    const result = this.landmarker.detectForVideo(v, ts);
    const raw = this._classify(result);

    const now = Date.now();
    this.history.push([now, raw]);
    while (this.history.length && now - this.history[0][0] > SMOOTHING_WINDOW_MS) this.history.shift();

    const n = this.history.length;
    const focusedShare = this.history.filter(([, s]) => s === FOCUSED).length / n;
    const awayShare = this.history.filter(([, s]) => s === AWAY).length / n;
    const { share } = SENSITIVITY[this.sensitivity] || SENSITIVITY[2];
    let state = DISTRACTED;
    if (focusedShare >= share) state = FOCUSED;
    else if (awayShare >= 0.5) state = AWAY;
    this.onState(state, focusedShare);
  }

  _classify(result) {
    const ctx = this.ctx;
    const W = this.canvas.width, H = this.canvas.height;
    ctx.clearRect(0, 0, W, H);

    const lm = result.faceLandmarks?.[0];
    if (!lm) return AWAY;

    const cfg = SENSITIVITY[this.sensitivity] || SENSITIVITY[2];
    const angle = headTurnDegrees(result, lm);
    const blink = blinkScore(result);
    const state = angle > cfg.maxAngle || blink > cfg.blink ? DISTRACTED : FOCUSED;

    // overlay: corner box around the face + rings on the eyes
    let x1 = 1, y1 = 1, x2 = 0, y2 = 0;
    for (const p of lm) {
      if (p.x < x1) x1 = p.x; if (p.x > x2) x2 = p.x;
      if (p.y < y1) y1 = p.y; if (p.y > y2) y2 = p.y;
    }
    const color = BOX_COLORS[state];
    drawCornerBox(ctx, x1 * W, y1 * H, x2 * W, y2 * H, color);
    const eyeR = Math.max(6, ((x2 - x1) * W) / 12);
    ctx.lineWidth = 2;
    ctx.strokeStyle = color;
    for (const i of [468, 473].filter((i) => lm[i]).length ? [468, 473] : [159, 386]) {
      ctx.beginPath();
      ctx.arc(lm[i].x * W, lm[i].y * H, eyeR, 0, Math.PI * 2);
      ctx.stroke();
    }
    return state;
  }
}

// Largest of head pitch / yaw, in degrees, from the facial transformation matrix.
function headTurnDegrees(result, lm) {
  const m = result.facialTransformationMatrixes?.[0]?.data;
  if (m && m.length === 16) {
    // column-major 4x4: r(i, j) = m[j * 4 + i]
    const r = (i, j) => m[j * 4 + i];
    const yaw = Math.asin(Math.max(-1, Math.min(1, -r(2, 0))));
    const pitch = Math.atan2(r(2, 1), r(2, 2));
    return (Math.max(Math.abs(yaw), Math.abs(pitch)) * 180) / Math.PI;
  }
  // fallback: how far the nose tip sits from the middle of the face, as a rough yaw
  const nose = lm[1], left = lm[234], right = lm[454];
  const ratio = (nose.x - left.x) / (right.x - left.x || 1);
  return Math.abs(ratio - 0.5) * 120;
}

function blinkScore(result) {
  const cats = result.faceBlendshapes?.[0]?.categories;
  if (!cats) return 0;
  const get = (name) => cats.find((c) => c.categoryName === name)?.score ?? 0;
  return Math.min(get("eyeBlinkLeft"), get("eyeBlinkRight"));
}

function drawCornerBox(ctx, x1, y1, x2, y2, color) {
  const len = Math.max(12, (x2 - x1) / 5);
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  for (const [cx, cy, dx, dy] of [[x1, y1, 1, 1], [x2, y1, -1, 1], [x1, y2, 1, -1], [x2, y2, -1, -1]]) {
    ctx.beginPath();
    ctx.moveTo(cx + dx * len, cy);
    ctx.lineTo(cx, cy);
    ctx.lineTo(cx, cy + dy * len);
    ctx.stroke();
  }
}

function friendlyError(err) {
  const name = err?.name || "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return "Camera permission was blocked. Allow camera access for this site in your browser's address bar, then try again.";
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return "No camera was found. Check that one is connected, or pick a different camera in Settings.";
  if (name === "NotReadableError")
    return "The camera is busy. Close other apps using it (Zoom, FaceTime…) and try again.";
  if (err?.message?.includes("fetch") || err?.message?.includes("import"))
    return "Couldn't load the face-tracking model. Check your internet connection and try again.";
  return err?.message || "Couldn't start the camera.";
}

export async function listCameras() {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((d) => d.kind === "videoinput");
}
