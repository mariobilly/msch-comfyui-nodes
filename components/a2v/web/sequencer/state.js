// Single source of truth for the Sequencer modal. Nothing outside this
// module mutates schedule state directly -- waveform.js/timeline.js/
// inspector.js/transport.js/modal.js all go through the exported `state`
// singleton's methods and subscribe() to re-render on change.

export const GRIDS = ["every_beat", "half", "quarter", "bar"];
export const CURVES = ["linear", "ease"];
export const GRID_BEAT_STEP = { every_beat: 1, half: 0.5, quarter: 0.25, bar: 4 };

function uid(prefix = "b") {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

// JS port of mscha2v/core/drift.py::beats_to_frame_boundaries -- kept in
// sync by hand with the Python original (no automated cross-check exists
// yet; see DECISIONS.md "Flagged risks"). Used only for the live in-modal
// preview -- the backend MschA2V_ShotPlanner node recomputes the
// authoritative frame boundaries from start_beat/end_beat at compile time.
export function beatsToFrameBoundaries(boundaryTimesSec, fps) {
  const frames = [];
  let emitted = 0;
  for (const t of boundaryTimesSec) {
    const exact = t * fps;
    let n = Math.round(exact) - emitted;
    n = emitted > 0 ? Math.max(n, 1) : Math.max(n, 0);
    emitted += n;
    frames.push(emitted);
  }
  return frames;
}

function emptyBeatMap() {
  return {
    duration_sec: 0,
    sr: 44100,
    bpm: 0,
    beats_sec: [],
    onsets_sec: [],
    downbeats_sec: [],
    analysis_source: "full",
    offset_ms: 0,
  };
}

class SequencerState {
  constructor() {
    this.listeners = new Set();
    this.reset();
  }

  reset() {
    this.audioPath = "";
    this.beatMap = emptyBeatMap();
    this.grid = "every_beat";
    this.curve = "linear";
    this.fps = 24;
    this.totalFrames = 0;
    this.masterSeed = 0;
    this.blocks = [];
    this.selection = new Set();
    this.halfTime = false;
    // In-modal file browser state (not part of the saved Schedule).
    this.audioFiles = [];
    this.fileSearchQuery = "";
    this.sourceTab = "comfy"; // "comfy" | "local"
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  _emit() {
    for (const fn of this.listeners) fn(this);
  }

  loadFromScheduleJson(text) {
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (err) {
      console.warn("MschA2V: schedule_json failed to parse, starting fresh", err);
    }
    this.reset();
    if (data && data.beat_map) {
      this.audioPath = data.audio_path || "";
      this.beatMap = data.beat_map;
      this.grid = GRIDS.includes(data.grid) ? data.grid : "every_beat";
      this.curve = CURVES.includes(data.curve) ? data.curve : "linear";
      this.fps = data.fps || 24;
      this.totalFrames = data.total_frames || 0;
      this.masterSeed = data.master_seed || 0;
      this.blocks = (data.blocks || []).map((b) => ({ ...b }));
    }
    this.recomputeFrames();
    this._emit();
  }

  toScheduleJson() {
    this.recomputeFrames();
    const schedule = {
      version: 1,
      fps: this.fps,
      total_frames: this.totalFrames,
      audio_path: this.audioPath,
      beat_map: this.beatMap || emptyBeatMap(),
      grid: this.grid,
      curve: this.curve,
      blocks: this.blocks.map((b) => ({ ...b })),
      master_seed: this.masterSeed,
    };
    return JSON.stringify(schedule);
  }

  // Mirrors mscha2v/core/schedule.py::_beat_to_seconds.
  beatToSeconds(beatIndex) {
    const beats = (this.beatMap && this.beatMap.beats_sec) || [];
    const bpm = (this.beatMap && this.beatMap.bpm) || 0;
    const fallbackInterval = bpm > 0 ? 60.0 / bpm : 0.5;
    if (!beats.length) return beatIndex * fallbackInterval;
    const n = beats.length;
    if (beatIndex <= 0) {
      const interval = n > 1 ? beats[1] - beats[0] : fallbackInterval;
      return beats[0] + beatIndex * interval;
    }
    if (beatIndex >= n - 1) {
      const interval = n > 1 ? beats[n - 1] - beats[n - 2] : fallbackInterval;
      return beats[n - 1] + (beatIndex - (n - 1)) * interval;
    }
    const lo = Math.floor(beatIndex);
    const frac = beatIndex - lo;
    return beats[lo] + frac * (beats[lo + 1] - beats[lo]);
  }

  // Mirrors mscha2v/core/schedule.py::_resolve_frame_boundaries -- applies
  // drift correction across the WHOLE timeline at once so the live preview
  // matches what the backend will compile.
  recomputeFrames() {
    if (!this.blocks.length) return;
    const beatsSet = new Set();
    for (const b of this.blocks) {
      beatsSet.add(b.start_beat);
      beatsSet.add(b.end_beat);
    }
    const boundaryBeats = Array.from(beatsSet).sort((a, b) => a - b);
    const boundarySecs = boundaryBeats.map((beat) => this.beatToSeconds(beat));
    const boundaryFrames = beatsToFrameBoundaries(boundarySecs, this.fps);
    const beatToFrame = new Map(boundaryBeats.map((beat, i) => [beat, boundaryFrames[i]]));
    for (const b of this.blocks) {
      b.start_frame = beatToFrame.get(b.start_beat) ?? b.start_frame;
      b.end_frame = beatToFrame.get(b.end_beat) ?? b.end_frame;
    }
  }

  // Inverse of beatToSeconds -- continuous (non-grid-snapped) seconds ->
  // fractional beat index, used while dragging blocks so movement tracks
  // the cursor smoothly; snapping to the grid happens only when the drag
  // value is committed.
  secondsToBeatIndex(seconds) {
    const beats = (this.beatMap && this.beatMap.beats_sec) || [];
    const bpm = (this.beatMap && this.beatMap.bpm) || 0;
    const fallbackInterval = bpm > 0 ? 60.0 / bpm : 0.5;
    if (!beats.length) return seconds / fallbackInterval;
    const n = beats.length;
    if (seconds <= beats[0]) {
      const interval = n > 1 ? beats[1] - beats[0] : fallbackInterval;
      return (seconds - beats[0]) / (interval || 1e-9);
    }
    if (seconds >= beats[n - 1]) {
      const interval = n > 1 ? beats[n - 1] - beats[n - 2] : fallbackInterval;
      return n - 1 + (seconds - beats[n - 1]) / (interval || 1e-9);
    }
    let lo = 0;
    let hi = n - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (beats[mid] <= seconds) lo = mid;
      else hi = mid;
    }
    const frac = (seconds - beats[lo]) / (beats[hi] - beats[lo] || 1e-9);
    return lo + frac;
  }

  snapBeatToGrid(beat) {
    const step = GRID_BEAT_STEP[this.grid] ?? 1;
    return Math.round(beat / step) * step;
  }

  secondsToNearestGridBeat(seconds) {
    // Find the fractional beat index closest to `seconds` via a coarse
    // linear scan over detected beats (modal-sized lists, fine to scan).
    const beats = (this.beatMap && this.beatMap.beats_sec) || [];
    if (!beats.length) {
      const bpm = (this.beatMap && this.beatMap.bpm) || 120;
      return this.snapBeatToGrid(seconds / (60.0 / bpm));
    }
    let bestIdx = 0;
    let bestDist = Infinity;
    for (let i = 0; i < beats.length; i++) {
      const d = Math.abs(beats[i] - seconds);
      if (d < bestDist) {
        bestDist = d;
        bestIdx = i;
      }
    }
    return this.snapBeatToGrid(bestIdx);
  }

  addBlock(startBeat, endBeat, opts = {}) {
    const block = {
      id: uid(),
      prompt: opts.prompt ?? "",
      negative: opts.negative ?? "",
      start_beat: startBeat,
      end_beat: endBeat,
      start_frame: 0,
      end_frame: 0,
      fade_in_frames: opts.fade_in_frames ?? 0,
      fade_out_frames: opts.fade_out_frames ?? 0,
      crossfade_frames: opts.crossfade_frames ?? 0,
      group_id: opts.group_id ?? null,
      seed: opts.seed ?? null,
      ref_image_slot: null,
      ref_audio_slot: null,
    };
    this.blocks.push(block);
    this.blocks.sort((a, b) => a.start_beat - b.start_beat);
    this.recomputeFrames();
    this._emit();
    return block;
  }

  updateBlock(id, patch) {
    const block = this.blocks.find((b) => b.id === id);
    if (!block) return;
    Object.assign(block, patch);
    this.blocks.sort((a, b) => a.start_beat - b.start_beat);
    this.recomputeFrames();
    this._emit();
  }

  deleteBlock(id) {
    this.blocks = this.blocks.filter((b) => b.id !== id);
    this.selection.delete(id);
    this._emit();
  }

  deleteSelected() {
    if (!this.selection.size) return;
    this.blocks = this.blocks.filter((b) => !this.selection.has(b.id));
    this.selection.clear();
    this._emit();
  }

  splitBlock(id, atBeat) {
    const idx = this.blocks.findIndex((b) => b.id === id);
    if (idx === -1) return null;
    const block = this.blocks[idx];
    if (atBeat <= block.start_beat || atBeat >= block.end_beat) return null;
    const second = { ...block, id: uid(), start_beat: atBeat };
    block.end_beat = atBeat;
    this.blocks.splice(idx + 1, 0, second);
    this.recomputeFrames();
    this._emit();
    return second;
  }

  duplicateBlock(id) {
    const block = this.blocks.find((b) => b.id === id);
    if (!block) return null;
    const span = block.end_beat - block.start_beat;
    const copy = {
      ...block,
      id: uid(),
      start_beat: block.end_beat,
      end_beat: block.end_beat + span,
      group_id: null,
    };
    this.blocks.push(copy);
    this.blocks.sort((a, b) => a.start_beat - b.start_beat);
    this.recomputeFrames();
    this._emit();
    return copy;
  }

  nudgeSelected(direction) {
    const step = GRID_BEAT_STEP[this.grid] ?? 1;
    const delta = direction * step;
    for (const id of this.selection) {
      const block = this.blocks.find((b) => b.id === id);
      if (!block) continue;
      block.start_beat += delta;
      block.end_beat += delta;
    }
    this.blocks.sort((a, b) => a.start_beat - b.start_beat);
    this.recomputeFrames();
    this._emit();
  }

  // Group ids double as their user-visible name ("Header 1", "Header 2", ...)
  // -- there is no separate name field in the Block schema, so the group_id
  // string itself IS the label shown on the group header bar. Renaming just
  // rewrites group_id on every member block.
  nextGroupName() {
    const existing = new Set(this.blocks.map((b) => b.group_id).filter(Boolean));
    let n = 1;
    while (existing.has(`Header ${n}`)) n++;
    return `Header ${n}`;
  }

  groupSelected() {
    if (this.selection.size < 2) return;
    const name = this.nextGroupName();
    for (const b of this.blocks) if (this.selection.has(b.id)) b.group_id = name;
    this._emit();
  }

  renameGroup(oldName, newName) {
    newName = (newName || "").trim();
    if (!newName || newName === oldName) return;
    for (const b of this.blocks) if (b.group_id === oldName) b.group_id = newName;
    this._emit();
  }

  ungroupBlock(id) {
    const block = this.blocks.find((b) => b.id === id);
    if (!block || !block.group_id) return;
    const groupId = block.group_id;
    for (const b of this.blocks) if (b.group_id === groupId) b.group_id = null;
    this._emit();
  }

  groupInfo() {
    // -> Map<groupId, {name, blockIds, startBeat, endBeat}> in timeline order.
    const groups = new Map();
    for (const b of this.blocks) {
      if (!b.group_id) continue;
      if (!groups.has(b.group_id)) {
        groups.set(b.group_id, { name: b.group_id, blockIds: [], startBeat: b.start_beat, endBeat: b.end_beat });
      }
      const g = groups.get(b.group_id);
      g.blockIds.push(b.id);
      g.startBeat = Math.min(g.startBeat, b.start_beat);
      g.endBeat = Math.max(g.endBeat, b.end_beat);
    }
    return groups;
  }

  setSelection(ids) {
    this.selection = new Set(ids);
    this._emit();
  }

  toggleSelection(id) {
    if (this.selection.has(id)) this.selection.delete(id);
    else this.selection.add(id);
    this._emit();
  }

  setAudioFiles(files) {
    this.audioFiles = files || [];
    this._emit();
  }

  setFileSearchQuery(q) {
    this.fileSearchQuery = q || "";
    this._emit();
  }

  filteredAudioFiles() {
    const q = this.fileSearchQuery.trim().toLowerCase();
    if (!q) return this.audioFiles;
    return this.audioFiles.filter((f) => f.path.toLowerCase().includes(q));
  }
}

export const state = new SequencerState();
