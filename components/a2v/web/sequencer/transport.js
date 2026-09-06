// WebAudio-backed transport: play/pause/stop, loop-between-handles, and a
// rAF-driven playhead tick. Knows nothing about ComfyUI routes -- the
// audio URL is supplied by the caller (modal.js) via getAudioUrl().

export class TransportView {
  constructor(opts = {}) {
    this.getAudioUrl = opts.getAudioUrl || (() => null);
    this.onTick = opts.onTick || (() => {});
    this.audioEl = new Audio();
    this.audioEl.preload = "auto";
    this.loopStart = null;
    this.loopEnd = null;
    this._rafId = null;
    this._boundTick = this._tick.bind(this);
  }

  destroy() {
    this.stop();
    this.audioEl.src = "";
  }

  setLoop(start, end) {
    this.loopStart = start;
    this.loopEnd = end;
  }

  async play() {
    const url = this.getAudioUrl();
    if (!url) return;
    if (!this.audioEl.src || !this.audioEl.src.endsWith(url)) {
      this.audioEl.src = url;
    }
    try {
      await this.audioEl.play();
    } catch (err) {
      console.warn("MschA2V: audio playback failed", err);
      return;
    }
    this._startLoop();
  }

  pause() {
    this.audioEl.pause();
    this._stopLoop();
  }

  stop() {
    this.audioEl.pause();
    this.audioEl.currentTime = 0;
    this._stopLoop();
    this.onTick(0);
  }

  seek(sec) {
    this.audioEl.currentTime = Math.max(0, sec);
    this.onTick(this.audioEl.currentTime);
  }

  get isPlaying() {
    return !this.audioEl.paused && !this.audioEl.ended;
  }

  toggle() {
    if (this.isPlaying) this.pause();
    else this.play();
  }

  _startLoop() {
    this._stopLoop();
    this._rafId = requestAnimationFrame(this._boundTick);
  }

  _stopLoop() {
    if (this._rafId) cancelAnimationFrame(this._rafId);
    this._rafId = null;
  }

  _tick() {
    if (this.loopStart != null && this.loopEnd != null && this.audioEl.currentTime >= this.loopEnd) {
      this.audioEl.currentTime = this.loopStart;
    }
    this.onTick(this.audioEl.currentTime);
    if (!this.audioEl.paused) {
      this._rafId = requestAnimationFrame(this._boundTick);
    }
  }
}
