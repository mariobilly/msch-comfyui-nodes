import { api } from "../../../../scripts/api.js";

const MIN_VIEW_SECONDS = 0.5;

export class WaveformView {
  constructor(canvas, state, opts = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.state = state;
    this.getAudioPath = opts.getAudioPath || (() => state.audioPath);
    this.onSeek = opts.onSeek || (() => {});
    this.onLoopChange = opts.onLoopChange || (() => {});

    this.viewStart = 0;
    this.viewEnd = Math.max(state.beatMap?.duration_sec || 30, MIN_VIEW_SECONDS);
    this.peaks = [];
    this.playheadSec = 0;
    this.loopStart = null;
    this.loopEnd = null;
    this._draggingLoop = null; // "start" | "end" | "region" | null
    this._fetchTimer = null;
    this._resizeObserver = null;

    this._bindEvents();
    this._observeResize();
    this.refreshPeaks();
  }

  destroy() {
    if (this._resizeObserver) this._resizeObserver.disconnect();
  }

  _observeResize() {
    this._resizeObserver = new ResizeObserver(() => this.render());
    this._resizeObserver.observe(this.canvas);
  }

  setPlayhead(sec) {
    this.playheadSec = sec;
    this.render();
  }

  setDuration(durationSec) {
    this.viewEnd = Math.max(durationSec, MIN_VIEW_SECONDS);
    this.viewStart = 0;
    this.refreshPeaks();
  }

  secToX(sec) {
    const w = this.canvas.clientWidth;
    const span = Math.max(this.viewEnd - this.viewStart, 1e-6);
    return ((sec - this.viewStart) / span) * w;
  }

  xToSec(x) {
    const w = this.canvas.clientWidth || 1;
    const span = this.viewEnd - this.viewStart;
    return this.viewStart + (x / w) * span;
  }

  async refreshPeaks() {
    const path = this.getAudioPath();
    if (!path) {
      this.peaks = [];
      this.render();
      return;
    }
    clearTimeout(this._fetchTimer);
    this._fetchTimer = setTimeout(async () => {
      try {
        const px = Math.max(64, Math.min(8000, Math.round(this.canvas.clientWidth * (window.devicePixelRatio || 1))));
        const params = new URLSearchParams({
          path,
          px: String(px),
          t0: String(this.viewStart),
          t1: String(this.viewEnd),
        });
        const res = await api.fetchApi(`/mscha2v/waveform?${params}`);
        const data = await res.json();
        this.peaks = data.peaks || [];
      } catch (err) {
        console.warn("MschA2V: waveform fetch failed", err);
        this.peaks = [];
      }
      this.render();
    }, 60);
  }

  _bindEvents() {
    this.canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const span = this.viewEnd - this.viewStart;
      const mouseSec = this.xToSec(e.offsetX);
      const zoomFactor = e.deltaY < 0 ? 0.85 : 1.15;
      let newSpan = Math.max(MIN_VIEW_SECONDS, span * zoomFactor);
      const duration = this.state.beatMap?.duration_sec || newSpan;
      newSpan = Math.min(newSpan, Math.max(duration, MIN_VIEW_SECONDS) * 4);
      const ratio = (mouseSec - this.viewStart) / (span || 1);
      this.viewStart = mouseSec - ratio * newSpan;
      this.viewEnd = this.viewStart + newSpan;
      if (this.viewStart < 0) {
        this.viewEnd -= this.viewStart;
        this.viewStart = 0;
      }
      this.refreshPeaks();
    }, { passive: false });

    let panStart = null;
    this.canvas.addEventListener("pointerdown", (e) => {
      const handle = this._hitLoopHandle(e.offsetX);
      if (handle) {
        this._draggingLoop = handle;
        this.canvas.setPointerCapture(e.pointerId);
        return;
      }
      if (e.shiftKey) {
        this.loopStart = this.xToSec(e.offsetX);
        this.loopEnd = this.loopStart;
        this._draggingLoop = "end";
        this.canvas.setPointerCapture(e.pointerId);
        return;
      }
      if (e.button === 2) return;
      panStart = { x: e.offsetX, viewStart: this.viewStart, viewEnd: this.viewEnd };
    });

    this.canvas.addEventListener("pointermove", (e) => {
      if (this._draggingLoop) {
        const sec = this.xToSec(e.offsetX);
        if (this._draggingLoop === "start") this.loopStart = sec;
        else if (this._draggingLoop === "end") this.loopEnd = sec;
        if (this.loopStart != null && this.loopEnd != null && this.loopStart > this.loopEnd) {
          [this.loopStart, this.loopEnd] = [this.loopEnd, this.loopStart];
        }
        this.render();
        return;
      }
      if (panStart) {
        const w = this.canvas.clientWidth || 1;
        const span = panStart.viewEnd - panStart.viewStart;
        const dxSec = ((e.offsetX - panStart.x) / w) * span;
        this.viewStart = panStart.viewStart - dxSec;
        this.viewEnd = panStart.viewEnd - dxSec;
        this.render();
      }
    });

    this.canvas.addEventListener("pointerup", (e) => {
      if (this._draggingLoop) {
        this._draggingLoop = null;
        this.onLoopChange(this.loopStart, this.loopEnd);
        return;
      }
      if (panStart) {
        const moved = Math.abs(e.offsetX - panStart.x) > 3;
        panStart = null;
        if (!moved) this.onSeek(this.xToSec(e.offsetX));
        this.refreshPeaks();
      }
    });

    this.canvas.addEventListener("dblclick", () => {
      this.loopStart = null;
      this.loopEnd = null;
      this.onLoopChange(null, null);
      this.render();
    });
  }

  _hitLoopHandle(x) {
    if (this.loopStart == null || this.loopEnd == null) return null;
    const sx = this.secToX(this.loopStart);
    const ex = this.secToX(this.loopEnd);
    if (Math.abs(x - sx) < 6) return "start";
    if (Math.abs(x - ex) < 6) return "end";
    return null;
  }

  render() {
    const canvas = this.canvas;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 300;
    const h = canvas.clientHeight || 120;
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    const ctx = this.ctx;
    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    ctx.fillStyle = "#14121a";
    ctx.fillRect(0, 0, w, h);

    const rulerH = 20;
    this._renderRuler(ctx, w, rulerH);

    const h2 = h - rulerH;
    ctx.save();
    ctx.translate(0, rulerH);

    // Loop region
    if (this.loopStart != null && this.loopEnd != null) {
      const sx = this.secToX(this.loopStart);
      const ex = this.secToX(this.loopEnd);
      ctx.fillStyle = "rgba(123, 47, 247, 0.15)";
      ctx.fillRect(sx, 0, ex - sx, h2);
    }

    // Waveform
    const mid = h2 / 2;
    if (this.peaks.length) {
      ctx.strokeStyle = "#18b5b0";
      ctx.beginPath();
      const step = w / this.peaks.length;
      for (let i = 0; i < this.peaks.length; i++) {
        const [mn, mx] = this.peaks[i];
        const x = i * step;
        ctx.moveTo(x, mid + mn * mid * 0.95);
        ctx.lineTo(x, mid + mx * mid * 0.95);
      }
      ctx.stroke();
    } else {
      ctx.strokeStyle = "#3a3648";
      ctx.beginPath();
      ctx.moveTo(0, mid);
      ctx.lineTo(w, mid);
      ctx.stroke();
    }

    // Beat ticks
    const beats = this.state.beatMap?.beats_sec || [];
    ctx.strokeStyle = "rgba(123, 47, 247, 0.55)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const t of beats) {
      if (t < this.viewStart || t > this.viewEnd) continue;
      const x = this.secToX(t);
      ctx.moveTo(x, h2 - 10);
      ctx.lineTo(x, h2);
    }
    ctx.stroke();

    // Downbeats (taller ticks)
    const downbeats = this.state.beatMap?.downbeats_sec || [];
    ctx.strokeStyle = "#7b2ff7";
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (const t of downbeats) {
      if (t < this.viewStart || t > this.viewEnd) continue;
      const x = this.secToX(t);
      ctx.moveTo(x, h2 - 18);
      ctx.lineTo(x, h2);
    }
    ctx.stroke();

    // Loop handles
    if (this.loopStart != null && this.loopEnd != null) {
      ctx.fillStyle = "#7b2ff7";
      for (const t of [this.loopStart, this.loopEnd]) {
        const x = this.secToX(t);
        ctx.fillRect(x - 2, 0, 4, h2);
      }
    }

    // Playhead
    if (this.playheadSec >= this.viewStart && this.playheadSec <= this.viewEnd) {
      const x = this.secToX(this.playheadSec);
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h2);
      ctx.stroke();
    }

    ctx.restore(); // matches the inner save() before the ruler-offset translate
    ctx.restore(); // matches the outer save() at the top of render()
  }

  _renderRuler(ctx, w, rulerH) {
    ctx.fillStyle = "#0c0a10";
    ctx.fillRect(0, 0, w, rulerH);
    ctx.strokeStyle = "#2a2534";
    ctx.beginPath();
    ctx.moveTo(0, rulerH - 0.5);
    ctx.lineTo(w, rulerH - 0.5);
    ctx.stroke();

    const fps = this.state.fps || 24;
    const span = Math.max(this.viewEnd - this.viewStart, 1e-6);
    // Aim for a tick roughly every ~70px, snapped to a "nice" frame count.
    const approxFrameStep = (span * fps) / (w / 70);
    const niceSteps = [12, 24, 48, 96, 192, 384, 768, 1536, 3072];
    const frameStep = niceSteps.find((s) => s >= approxFrameStep) || niceSteps[niceSteps.length - 1];

    ctx.fillStyle = "#8f89a3";
    ctx.strokeStyle = "#3a3648";
    ctx.font = "10px monospace";
    ctx.lineWidth = 1;
    ctx.beginPath();
    const startFrame = Math.floor((this.viewStart * fps) / frameStep) * frameStep;
    const endFrame = Math.ceil((this.viewEnd * fps) / frameStep) * frameStep;
    for (let f = startFrame; f <= endFrame; f += frameStep) {
      const sec = f / fps;
      if (sec < this.viewStart || sec > this.viewEnd) continue;
      const x = this.secToX(sec);
      ctx.moveTo(x, rulerH - 6);
      ctx.lineTo(x, rulerH);
      ctx.fillText(`${f}f`, x + 3, rulerH - 8);
    }
    ctx.stroke();
  }
}
