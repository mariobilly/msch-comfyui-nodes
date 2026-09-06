const PALETTE = ["#7b2ff7", "#18b5b0", "#f7a72f", "#e0507a", "#4f8ef7", "#9bd35a"];
const MIN_SPAN_BEATS = 0.05;
const HEADER_H = 22;

export class TimelineView {
  constructor(canvas, state, waveformView, opts = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.state = state;
    this.wave = waveformView;
    this.onInspect = opts.onInspect || (() => {});

    this._drag = null;
    this._bindEvents();
    this._resizeObserver = new ResizeObserver(() => this.render());
    this._resizeObserver.observe(canvas);
    this._unsubscribe = this.state.subscribe(() => this.render());
    this.render();
  }

  destroy() {
    this._resizeObserver.disconnect();
    this._unsubscribe();
  }

  secToX(sec) {
    return this.wave.secToX(sec);
  }

  xToSec(x) {
    return this.wave.xToSec(x);
  }

  _beatToX(beat) {
    return this.secToX(this.state.beatToSeconds(beat));
  }

  _blockAtX(x) {
    for (const b of this.state.blocks) {
      const sx = this._beatToX(b.start_beat);
      const ex = this._beatToX(b.end_beat);
      if (x >= sx - 3 && x <= ex + 3) return b;
    }
    return null;
  }

  _groupAtX(x) {
    for (const g of this.state.groupInfo().values()) {
      const sx = this._beatToX(g.startBeat);
      const ex = this._beatToX(g.endBeat);
      if (x >= sx && x <= ex) return g;
    }
    return null;
  }

  _bindEvents() {
    const canvas = this.canvas;

    canvas.addEventListener("dblclick", (e) => {
      if (e.offsetY > HEADER_H) return;
      const group = this._groupAtX(e.offsetX);
      if (!group) return;
      const next = window.prompt("Rename group", group.name);
      if (next) this.state.renameGroup(group.name, next);
    });

    canvas.addEventListener("pointerdown", (e) => {
      if (e.button === 2) return;
      if (e.offsetY <= HEADER_H) return; // header strip only handles dblclick-to-rename
      const x = e.offsetX;
      const block = this._blockAtX(x);

      if (block) {
        const sx = this._beatToX(block.start_beat);
        const ex = this._beatToX(block.end_beat);
        let mode = "move";
        if (Math.abs(x - sx) < 6) mode = "resize-left";
        else if (Math.abs(x - ex) < 6) mode = "resize-right";

        if (e.shiftKey) {
          this.state.toggleSelection(block.id);
        } else if (!this.state.selection.has(block.id)) {
          this.state.setSelection([block.id]);
        }
        this.onInspect(block.id);

        this._drag = {
          mode,
          id: block.id,
          startBeatIndex: this.state.secondsToBeatIndex(this.xToSec(x)),
          origStart: block.start_beat,
          origEnd: block.end_beat,
        };
        canvas.setPointerCapture(e.pointerId);
      } else if (!e.shiftKey) {
        this.state.setSelection([]);
      }
    });

    canvas.addEventListener("pointermove", (e) => {
      if (!this._drag) return;
      const block = this.state.blocks.find((b) => b.id === this._drag.id);
      if (!block) return;
      const currentBeatIndex = this.state.secondsToBeatIndex(this.xToSec(e.offsetX));
      const rawDelta = currentBeatIndex - this._drag.startBeatIndex;

      if (this._drag.mode === "move") {
        const span = this._drag.origEnd - this._drag.origStart;
        const newStart = this.state.snapBeatToGrid(this._drag.origStart + rawDelta);
        block.start_beat = newStart;
        block.end_beat = newStart + span;
      } else if (this._drag.mode === "resize-left") {
        let newStart = this.state.snapBeatToGrid(this._drag.origStart + rawDelta);
        newStart = Math.min(newStart, this._drag.origEnd - MIN_SPAN_BEATS);
        block.start_beat = newStart;
      } else if (this._drag.mode === "resize-right") {
        let newEnd = this.state.snapBeatToGrid(this._drag.origEnd + rawDelta);
        newEnd = Math.max(newEnd, this._drag.origStart + MIN_SPAN_BEATS);
        block.end_beat = newEnd;
      }
      this.render();
    });

    canvas.addEventListener("pointerup", () => {
      if (this._drag) {
        this._drag = null;
        this.state.recomputeFrames();
        this.state._emit();
      }
    });

    canvas.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      this._showContextMenu(e);
    });
  }

  _groupColors() {
    const map = new Map();
    let i = 0;
    for (const b of this.state.blocks) {
      if (b.group_id && !map.has(b.group_id)) {
        map.set(b.group_id, PALETTE[i % PALETTE.length]);
        i++;
      }
    }
    return map;
  }

  _showContextMenu(e) {
    document.querySelectorAll(".mscha2v-ctx-menu").forEach((el) => el.remove());
    const block = this._blockAtX(e.offsetX);
    const menu = document.createElement("div");
    menu.className = "mscha2v-ctx-menu";
    menu.style.left = `${e.clientX}px`;
    menu.style.top = `${e.clientY}px`;

    const addItem = (label, fn, disabled = false) => {
      const item = document.createElement("div");
      item.className = "mscha2v-ctx-item" + (disabled ? " disabled" : "");
      item.textContent = label;
      if (!disabled) item.addEventListener("click", () => { fn(); menu.remove(); });
      menu.appendChild(item);
    };

    if (block) {
      addItem("Split here", () => {
        const beat = this.state.snapBeatToGrid(this.state.secondsToBeatIndex(this.xToSec(e.offsetX)));
        this.state.splitBlock(block.id, beat);
      });
      addItem("Duplicate", () => this.state.duplicateBlock(block.id));
      addItem("Delete", () => this.state.deleteBlock(block.id));
    }
    addItem("Group selected", () => this.state.groupSelected(), this.state.selection.size < 2);
    addItem(
      "Ungroup",
      () => { for (const id of this.state.selection) this.state.ungroupBlock(id); },
      this.state.selection.size < 1
    );

    document.body.appendChild(menu);
    const remove = (ev) => {
      if (!menu.contains(ev.target)) {
        menu.remove();
        document.removeEventListener("pointerdown", remove);
      }
    };
    setTimeout(() => document.addEventListener("pointerdown", remove), 0);
  }

  render() {
    const canvas = this.canvas;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 300;
    const h = canvas.clientHeight || 90;
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    const ctx = this.ctx;
    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0f0d14";
    ctx.fillRect(0, 0, w, h);

    const groupColors = this._groupColors();
    const fps = this.state.fps || 24;

    // Group header strip.
    ctx.fillStyle = "#151220";
    ctx.fillRect(0, 0, w, HEADER_H);
    for (const g of this.state.groupInfo().values()) {
      const sx = this._beatToX(g.startBeat);
      const ex = this._beatToX(g.endBeat);
      if (ex < 0 || sx > w) continue;
      const gw = Math.max(ex - sx, 2);
      ctx.fillStyle = groupColors.get(g.name) || "#3a3648";
      ctx.fillRect(sx, 2, gw, HEADER_H - 6);
      ctx.fillStyle = "#0c0a10";
      ctx.font = "600 10px -apple-system, sans-serif";
      ctx.save();
      ctx.beginPath();
      ctx.rect(sx + 4, 0, Math.max(gw - 8, 0), HEADER_H);
      ctx.clip();
      ctx.fillText(`${g.name} · ${g.blockIds.length} prompts`, sx + 6, HEADER_H - 9);
      ctx.restore();
    }
    ctx.strokeStyle = "#2a2534";
    ctx.beginPath();
    ctx.moveTo(0, HEADER_H - 0.5);
    ctx.lineTo(w, HEADER_H - 0.5);
    ctx.stroke();

    const laneTop = HEADER_H + 8;
    const laneBottom = h - 8;

    for (const block of this.state.blocks) {
      const sx = this._beatToX(block.start_beat);
      const ex = this._beatToX(block.end_beat);
      if (ex < 0 || sx > w) continue;
      const bw = Math.max(ex - sx, 2);
      const selected = this.state.selection.has(block.id);
      const baseColor = block.group_id ? groupColors.get(block.group_id) : "#3a3648";

      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(sx, laneTop, bw, laneBottom - laneTop, 4);
      else ctx.rect(sx, laneTop, bw, laneBottom - laneTop);
      ctx.fillStyle = selected ? "#7b2ff7" : baseColor;
      ctx.fill();
      ctx.strokeStyle = selected ? "#ffffff" : "rgba(255,255,255,0.18)";
      ctx.lineWidth = selected ? 2 : 1;
      ctx.stroke();

      if (block.fade_in_frames > 0) {
        ctx.fillStyle = "rgba(0,0,0,0.35)";
        ctx.beginPath();
        ctx.moveTo(sx, laneTop);
        ctx.lineTo(sx + Math.min(14, bw / 3), laneTop);
        ctx.lineTo(sx, laneBottom);
        ctx.closePath();
        ctx.fill();
      }
      if (block.fade_out_frames > 0) {
        ctx.fillStyle = "rgba(0,0,0,0.35)";
        ctx.beginPath();
        ctx.moveTo(ex, laneTop);
        ctx.lineTo(ex - Math.min(14, bw / 3), laneTop);
        ctx.lineTo(ex, laneBottom);
        ctx.closePath();
        ctx.fill();
      }
      if (block.crossfade_frames > 0) {
        ctx.strokeStyle = "rgba(24,181,176,0.9)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        const cw = Math.min(12, bw / 2);
        for (let i = -8; i < cw; i += 4) {
          ctx.moveTo(sx + i, laneBottom);
          ctx.lineTo(sx + i + 4, laneTop);
        }
        ctx.stroke();
      }

      ctx.save();
      ctx.beginPath();
      ctx.rect(sx + 4, laneTop, Math.max(bw - 8, 0), laneBottom - laneTop);
      ctx.clip();
      ctx.fillStyle = "#f2f0f6";
      ctx.font = "11px monospace";
      const text = (block.prompt || "").split("\n")[0];
      ctx.fillText(text, sx + 6, laneTop + 16);
      ctx.fillStyle = "rgba(242,240,246,0.55)";
      ctx.font = "10px monospace";
      const rangeText = `${block.start_frame}-${block.end_frame}f · ${(block.start_frame / fps).toFixed(2)}-${(block.end_frame / fps).toFixed(2)}s`;
      ctx.fillText(rangeText, sx + 6, laneBottom - 6);
      ctx.restore();
    }

    ctx.restore();
  }
}
