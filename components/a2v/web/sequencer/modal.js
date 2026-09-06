import { api } from "../../../../scripts/api.js";
import { InspectorView } from "./inspector.js";
import { state } from "./state.js";
import { TimelineView } from "./timeline.js";
import { TransportView } from "./transport.js";
import { WaveformView } from "./waveform.js";

let activeModal = null;

export function openSequencerModal({ node, audioPathWidget, scheduleWidget, onDone }) {
  if (activeModal) activeModal.close();
  activeModal = new SequencerModal({ node, audioPathWidget, scheduleWidget, onDone });
  activeModal.open();
}

function audioUrlFor(path) {
  if (!path) return null;
  const parts = path.split("/");
  const filename = parts.pop();
  const subfolder = parts.join("/");
  const params = new URLSearchParams({ filename, subfolder, type: "input" });
  return api.apiURL(`/view?${params}`);
}

async function uploadToInput(file) {
  const form = new FormData();
  form.append("image", file, file.name);
  form.append("type", "input");
  form.append("subfolder", "");
  form.append("overwrite", "true");
  const res = await api.fetchApi("/upload/image", { method: "POST", body: form });
  if (!res.ok) throw new Error(`upload failed (HTTP ${res.status})`);
  const data = await res.json();
  return data.subfolder ? `${data.subfolder}/${data.name}` : data.name;
}

const GRID_BEAT_STEP = { every_beat: 1, half: 0.5, quarter: 0.25, bar: 4 };
const AUDIO_VIDEO_EXT = /\.(wav|mp3|flac|ogg|m4a|aac|opus|mp4|mov|webm|mkv)$/i;

function formatTimecode(sec) {
  const ms = Math.floor((sec % 1) * 1000);
  const s = Math.floor(sec) % 60;
  const m = Math.floor(sec / 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

class SequencerModal {
  constructor({ node, audioPathWidget, scheduleWidget, onDone }) {
    this.node = node;
    this.audioPathWidget = audioPathWidget;
    this.scheduleWidget = scheduleWidget;
    this.onDone = onDone;
    this.root = null;
    this.autoAnalyze = true;
    this._localFiles = []; // File[] picked via "Choose folder", not yet uploaded
    this._keydownHandler = this._onKeydown.bind(this);
  }

  open() {
    const audioPath = this.audioPathWidget?.value || state.audioPath || "";
    state.loadFromScheduleJson(this.scheduleWidget?.value || "{}");
    if (audioPath) state.audioPath = audioPath;

    this._buildDom();
    document.addEventListener("keydown", this._keydownHandler);

    this.transport = new TransportView({
      getAudioUrl: () => audioUrlFor(state.audioPath),
      onTick: (sec) => this._onTick(sec),
    });

    this.wave = new WaveformView(this.waveformCanvas, state, {
      getAudioPath: () => state.audioPath,
      onSeek: (sec) => this.transport.seek(Math.max(0, sec)),
      onLoopChange: (a, b) => this.transport.setLoop(a, b),
    });
    this.timeline = new TimelineView(this.timelineCanvas, state, this.wave, {
      onInspect: (id) => this.inspector.inspect(id),
    });
    this.inspector = new InspectorView(this.inspectorEl, state);

    this._unsubscribe = state.subscribe(() => this._renderTopBar());
    this._renderTopBar();
    this._refreshFileList();

    if (state.beatMap?.duration_sec) {
      this.wave.setDuration(state.beatMap.duration_sec);
    } else if (state.audioPath && this.autoAnalyze) {
      this._analyze();
    }
  }

  close() {
    document.removeEventListener("keydown", this._keydownHandler);
    if (this._unsubscribe) this._unsubscribe();
    this.wave?.destroy();
    this.timeline?.destroy();
    this.inspector?.destroy();
    this.transport?.destroy();
    this.root?.remove();
    if (activeModal === this) activeModal = null;
  }

  _save() {
    const json = state.toScheduleJson();
    if (this.scheduleWidget) {
      this.scheduleWidget.value = json;
      this.scheduleWidget.callback?.(json);
    }
    if (this.audioPathWidget && state.audioPath) {
      this.audioPathWidget.value = state.audioPath;
    }
  }

  _done() {
    this._save();
    this.close();
    this.onDone?.();
  }

  async _refreshFileList() {
    try {
      const res = await api.fetchApi("/mscha2v/files?dir=input&ext=audio");
      const files = await res.json();
      if (Array.isArray(files)) state.setAudioFiles(files);
    } catch (err) {
      console.warn("MschA2V: failed to list input audio files", err);
    }
  }

  async _selectAudioPath(path) {
    state.audioPath = path;
    state.beatMap = { ...state.beatMap, duration_sec: 0 };
    state._emit();
    if (this.autoAnalyze) await this._analyze();
  }

  async _handleUpload(file) {
    if (!file) return;
    this.analyzeBtn.disabled = true;
    try {
      const relPath = await uploadToInput(file);
      await this._refreshFileList();
      await this._selectAudioPath(relPath);
    } catch (err) {
      console.error("MschA2V: upload failed", err);
      alert(`MschA2V: upload failed — ${err.message || err}`);
    } finally {
      this.analyzeBtn.disabled = false;
    }
  }

  async _analyze() {
    if (!state.audioPath) return;
    this.analyzeBtn.textContent = "Analyzing…";
    this.analyzeBtn.disabled = true;
    try {
      const res = await api.fetchApi("/mscha2v/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: state.audioPath, source: this.analysisSourceSelect.value }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      state.beatMap = data;
      if (!state.totalFrames) state.totalFrames = Math.round(data.duration_sec * state.fps);
      this.wave.setDuration(data.duration_sec);
      state.recomputeFrames();
      state._emit();
    } catch (err) {
      console.error("MschA2V: analyze failed", err);
      alert(`MschA2V: audio analysis failed — ${err.message || err}`);
    } finally {
      this.analyzeBtn.textContent = "Analyze";
      this.analyzeBtn.disabled = false;
    }
  }

  _onTick(sec) {
    this.wave.setPlayhead(sec);
    this.timecodeEl.textContent = `${formatTimecode(sec)} / ${formatTimecode(state.beatMap?.duration_sec || 0)}`;
  }

  _onKeydown(e) {
    if (!this.root || !this.root.isConnected) return;
    const active = document.activeElement;
    const typing = active && (active.tagName === "TEXTAREA" || active.tagName === "INPUT");
    if (e.code === "Space" && !typing) {
      e.preventDefault();
      this.transport.toggle();
    } else if (e.key === "Delete" && !typing) {
      state.deleteSelected();
    } else if (e.key.toLowerCase() === "d" && (e.ctrlKey || e.metaKey) && !typing) {
      e.preventDefault();
      for (const id of Array.from(state.selection)) state.duplicateBlock(id);
    } else if (e.key === "ArrowLeft" && !typing) {
      state.nudgeSelected(-1);
    } else if (e.key === "ArrowRight" && !typing) {
      state.nudgeSelected(1);
    } else if (e.key === "Escape") {
      this.close();
    }
  }

  _addPromptBlock() {
    const playheadBeat = state.secondsToBeatIndex(this.transport.audioEl.currentTime || 0);
    const start = state.snapBeatToGrid(playheadBeat);
    const step = GRID_BEAT_STEP[state.grid] ?? 1;
    const block = state.addBlock(start, start + step, {
      fade_in_frames: this._defaultFadeIn(),
      fade_out_frames: this._defaultFadeOut(),
    });
    state.setSelection([block.id]);
    this.inspector.inspect(block.id);
  }

  _renderTopBar() {
    const bm = state.beatMap;
    const bpm = bm?.bpm ? bm.bpm.toFixed(2) : "—";
    const duration = bm?.duration_sec ? bm.duration_sec.toFixed(2) : "0.00";
    const nBeats = bm?.beats_sec?.length ?? 0;
    const nOnsets = bm?.onsets_sec?.length ?? 0;
    const offset = bm?.offset_ms ?? 0;
    this.readout.textContent =
      `${bpm} BPM · ${state.grid.replace("_", " ")} grid · ${nBeats} detected · ${nOnsets} onsets · ` +
      `${duration} sec · offset ${offset >= 0 ? "+" : ""}${offset.toFixed(0)} ms`;
    this.filenameReadout.textContent = state.audioPath || "(no audio selected)";
    document.title = state.audioPath ? `MschA2V — ${state.audioPath}` : "MschA2V Sequencer";
    this.subtitleEl.textContent = state.audioPath
      ? `${bpm} BPM · ${state.audioPath} — edits save directly to the node`
      : "no audio selected yet";
    this._renderFileList();
    if (this.transport) this._onTick(this.transport.audioEl.currentTime || 0);
  }

  _renderFileList() {
    const listEl = this.fileListEl;
    listEl.innerHTML = "";
    if (state.sourceTab === "comfy") {
      const files = state.filteredAudioFiles();
      this.fileCountEl.textContent = `${state.audioFiles.length} files available in ComfyUI input.`;
      for (const f of files) {
        const item = document.createElement("div");
        item.className = "mscha2v-file-item" + (f.path === state.audioPath ? " active" : "");
        const name = document.createElement("div");
        name.className = "mscha2v-file-name";
        name.textContent = f.path;
        const sub = document.createElement("div");
        sub.className = "mscha2v-file-sub";
        sub.textContent = "ComfyUI/Input";
        item.appendChild(name);
        item.appendChild(sub);
        item.addEventListener("click", () => this._selectAudioPath(f.path));
        listEl.appendChild(item);
      }
    } else {
      this.fileCountEl.textContent = `${this._localFiles.length} local files picked (click to upload + select).`;
      const q = state.fileSearchQuery.trim().toLowerCase();
      for (const file of this._localFiles) {
        if (q && !file.name.toLowerCase().includes(q)) continue;
        const item = document.createElement("div");
        item.className = "mscha2v-file-item";
        const name = document.createElement("div");
        name.className = "mscha2v-file-name";
        name.textContent = file.name;
        const sub = document.createElement("div");
        sub.className = "mscha2v-file-sub";
        sub.textContent = "Local (not yet uploaded)";
        item.appendChild(name);
        item.appendChild(sub);
        item.addEventListener("click", () => this._handleUpload(file));
        listEl.appendChild(item);
      }
    }
  }

  _buildDom() {
    const root = document.createElement("div");
    root.className = "mscha2v-modal-overlay";
    root.innerHTML = `
      <div class="mscha2v-modal">
        <div class="mscha2v-topbar">
          <div class="mscha2v-title-block">
            <h1 class="mscha2v-title">MschA2V Beat Prompt Sequencer</h1>
            <div class="mscha2v-subtitle"></div>
          </div>
          <button class="mscha2v-btn mscha2v-btn-primary" data-action="done">Done</button>
        </div>
        <div class="mscha2v-body">
          <div class="mscha2v-left-panel">
            <div class="mscha2v-panel-section">
              <h3>Audio source</h3>
              <div class="mscha2v-dropzone" data-action="dropzone">Drop an audio or video file here, or click to choose one</div>
              <div class="mscha2v-source-buttons">
                <button class="mscha2v-btn" data-action="choose-file">Choose file</button>
                <button class="mscha2v-btn" data-action="choose-folder">Choose folder</button>
              </div>
              <div class="mscha2v-file-count"></div>
              <div class="mscha2v-source-tabs">
                <button class="mscha2v-tab active" data-action="tab-comfy">Comfy input</button>
                <button class="mscha2v-tab" data-action="tab-local">Local folder</button>
              </div>
              <input class="mscha2v-search" type="text" placeholder="Search audio files" data-action="search" />
              <div class="mscha2v-file-list"></div>
              <button class="mscha2v-btn mscha2v-btn-block" data-action="refresh-files">Refresh input</button>
            </div>
            <div class="mscha2v-panel-section">
              <h3>Sequence settings</h3>
              <div class="mscha2v-settings-grid">
                <label class="mscha2v-field"><span>FPS</span><input type="number" data-action="fps" min="1" max="240" /></label>
                <label class="mscha2v-field"><span>Length (frames)</span><input type="number" data-action="total-frames" min="0" /></label>
                <label class="mscha2v-field"><span>Default fade in</span><input type="number" data-action="default-fade-in" min="0" /></label>
                <label class="mscha2v-field"><span>Default fade out</span><input type="number" data-action="default-fade-out" min="0" /></label>
              </div>
              <label class="mscha2v-field"><span>Master seed</span><input type="number" data-action="master-seed" min="0" /></label>
              <label class="mscha2v-field"><span>Curve</span>
                <select data-action="curve">
                  <option value="linear">linear</option>
                  <option value="ease">ease</option>
                </select>
              </label>
              <label class="mscha2v-field"><span>Analysis source</span>
                <select data-action="analysis-source">
                  <option value="full">full mix</option>
                  <option value="drums">drums</option>
                  <option value="percussive">percussive</option>
                </select>
              </label>
              <label class="mscha2v-inline-check"><input type="checkbox" data-action="half-time" /> Half-time</label>
            </div>
          </div>
          <div class="mscha2v-main">
            <div class="mscha2v-toolbar-row">
              <button class="mscha2v-btn" data-action="play">▶ Play</button>
              <button class="mscha2v-btn" data-action="stop">■ Stop</button>
              <div class="mscha2v-timecode">00:00.000 / 00:00.000</div>
              <div class="mscha2v-filename-readout"></div>
              <div class="mscha2v-readout"></div>
              <label class="mscha2v-inline-check"><input type="checkbox" data-action="auto-analyze" checked /> Auto analyze</label>
              <button class="mscha2v-btn" data-action="analyze">Analyze</button>
              <button class="mscha2v-btn" data-action="separate-stems" disabled title="Not implemented yet">Separate stems</button>
            </div>
            <div class="mscha2v-toolbar-row mscha2v-toolbar-row-2">
              <label class="mscha2v-inline">Grid
                <select class="mscha2v-select" data-action="grid">
                  <option value="every_beat">every beat</option>
                  <option value="half">half</option>
                  <option value="quarter">quarter</option>
                  <option value="bar">bar</option>
                </select>
              </label>
              <label class="mscha2v-inline">Beat offset (ms)
                <input type="range" min="-100" max="100" step="1" data-action="offset" />
              </label>
              <span class="mscha2v-offset-readout"></span>
              <button class="mscha2v-btn" data-action="zero-offset">Zero</button>
            </div>
            <div class="mscha2v-waveform-wrap">
              <canvas class="mscha2v-waveform"></canvas>
            </div>
            <canvas class="mscha2v-timeline"></canvas>
            <div class="mscha2v-block-toolbar">
              <button class="mscha2v-btn" data-action="add-prompt">+ Prompt</button>
              <button class="mscha2v-btn" data-action="split">Split</button>
              <button class="mscha2v-btn" data-action="duplicate">Duplicate</button>
              <button class="mscha2v-btn" data-action="delete">Delete</button>
              <button class="mscha2v-btn" data-action="group">Group</button>
              <button class="mscha2v-btn" data-action="ungroup">Ungroup</button>
            </div>
            <div class="mscha2v-inspector"></div>
            <div class="mscha2v-hint">
              space play/pause · delete removes block · ctrl+D duplicate · ←/→ nudge one grid unit ·
              shift+click to multi-select · double-click a group header to rename it · right-click a block for more actions
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(root);
    this.root = root;

    this.subtitleEl = root.querySelector(".mscha2v-subtitle");
    this.readout = root.querySelector(".mscha2v-toolbar-row .mscha2v-readout");
    this.filenameReadout = root.querySelector(".mscha2v-filename-readout");
    this.timecodeEl = root.querySelector(".mscha2v-timecode");
    this.waveformCanvas = root.querySelector(".mscha2v-waveform");
    this.timelineCanvas = root.querySelector(".mscha2v-timeline");
    this.inspectorEl = root.querySelector(".mscha2v-inspector");
    this.analyzeBtn = root.querySelector('[data-action="analyze"]');
    this.analysisSourceSelect = root.querySelector('[data-action="analysis-source"]');
    this.analysisSourceSelect.value = state.beatMap?.analysis_source || "full";
    this.fileListEl = root.querySelector(".mscha2v-file-list");
    this.fileCountEl = root.querySelector(".mscha2v-file-count");
    const offsetReadout = root.querySelector(".mscha2v-offset-readout");

    const autoAnalyzeCheck = root.querySelector('[data-action="auto-analyze"]');
    autoAnalyzeCheck.checked = this.autoAnalyze;
    autoAnalyzeCheck.addEventListener("change", () => {
      this.autoAnalyze = autoAnalyzeCheck.checked;
    });

    const gridSelect = root.querySelector('[data-action="grid"]');
    gridSelect.value = state.grid;
    gridSelect.addEventListener("change", () => {
      state.grid = gridSelect.value;
      state._emit();
    });

    const curveSelect = root.querySelector('[data-action="curve"]');
    curveSelect.value = state.curve;
    curveSelect.addEventListener("change", () => {
      state.curve = curveSelect.value;
      state._emit();
    });

    const fpsInput = root.querySelector('[data-action="fps"]');
    fpsInput.value = state.fps;
    fpsInput.addEventListener("change", () => {
      state.fps = Number(fpsInput.value) || 24;
      state.recomputeFrames();
      state._emit();
    });

    const totalFramesInput = root.querySelector('[data-action="total-frames"]');
    totalFramesInput.value = state.totalFrames;
    totalFramesInput.addEventListener("change", () => {
      state.totalFrames = Number(totalFramesInput.value) || 0;
      state._emit();
    });

    const masterSeedInput = root.querySelector('[data-action="master-seed"]');
    masterSeedInput.value = state.masterSeed;
    masterSeedInput.addEventListener("change", () => {
      state.masterSeed = Number(masterSeedInput.value) || 0;
      state._emit();
    });

    const halfTimeCheck = root.querySelector('[data-action="half-time"]');
    halfTimeCheck.checked = state.halfTime;
    halfTimeCheck.addEventListener("change", () => {
      state.halfTime = halfTimeCheck.checked;
    });

    const defaultFadeIn = root.querySelector('[data-action="default-fade-in"]');
    const defaultFadeOut = root.querySelector('[data-action="default-fade-out"]');
    defaultFadeIn.value = 0;
    defaultFadeOut.value = 0;
    this._defaultFadeIn = () => Number(defaultFadeIn.value) || 0;
    this._defaultFadeOut = () => Number(defaultFadeOut.value) || 0;

    const offsetSlider = root.querySelector('[data-action="offset"]');
    const syncOffsetReadout = () => {
      const ms = Number(offsetSlider.value);
      offsetReadout.textContent = `${ms >= 0 ? "+" : ""}${ms} ms`;
    };
    offsetSlider.value = String(state.beatMap?.offset_ms ?? 0);
    syncOffsetReadout();
    offsetSlider.addEventListener("input", () => {
      if (state.beatMap) state.beatMap.offset_ms = Number(offsetSlider.value);
      syncOffsetReadout();
      state._emit();
    });
    root.querySelector('[data-action="zero-offset"]').addEventListener("click", () => {
      offsetSlider.value = "0";
      if (state.beatMap) state.beatMap.offset_ms = 0;
      syncOffsetReadout();
      state._emit();
    });

    // Audio source panel wiring.
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "audio/*,video/*";
    fileInput.style.display = "none";
    fileInput.addEventListener("change", () => this._handleUpload(fileInput.files?.[0]));
    root.appendChild(fileInput);

    const folderInput = document.createElement("input");
    folderInput.type = "file";
    folderInput.webkitdirectory = true;
    folderInput.multiple = true;
    folderInput.style.display = "none";
    folderInput.addEventListener("change", () => {
      this._localFiles = Array.from(folderInput.files || []).filter((f) => AUDIO_VIDEO_EXT.test(f.name));
      state.sourceTab = "local";
      this._setActiveTab("local");
      this._renderFileList();
    });
    root.appendChild(folderInput);

    root.querySelector('[data-action="choose-file"]').addEventListener("click", () => fileInput.click());
    root.querySelector('[data-action="choose-folder"]').addEventListener("click", () => folderInput.click());

    const dropzone = root.querySelector('[data-action="dropzone"]');
    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      const file = e.dataTransfer?.files?.[0];
      if (file) this._handleUpload(file);
    });

    const tabComfy = root.querySelector('[data-action="tab-comfy"]');
    const tabLocal = root.querySelector('[data-action="tab-local"]');
    this._setActiveTab = (tab) => {
      state.sourceTab = tab;
      tabComfy.classList.toggle("active", tab === "comfy");
      tabLocal.classList.toggle("active", tab === "local");
      this._renderFileList();
    };
    tabComfy.addEventListener("click", () => this._setActiveTab("comfy"));
    tabLocal.addEventListener("click", () => this._setActiveTab("local"));

    root.querySelector('[data-action="search"]').addEventListener("input", (e) => {
      state.setFileSearchQuery(e.target.value);
    });
    root.querySelector('[data-action="refresh-files"]').addEventListener("click", () => this._refreshFileList());

    root.querySelector('[data-action="analyze"]').addEventListener("click", () => this._analyze());
    root.querySelector('[data-action="done"]').addEventListener("click", () => this._done());
    root.querySelector('[data-action="add-prompt"]').addEventListener("click", () => this._addPromptBlock());
    root.querySelector('[data-action="split"]').addEventListener("click", () => {
      for (const id of Array.from(state.selection)) {
        const block = state.blocks.find((b) => b.id === id);
        if (block) state.splitBlock(id, (block.start_beat + block.end_beat) / 2);
      }
    });
    root.querySelector('[data-action="duplicate"]').addEventListener("click", () => {
      for (const id of Array.from(state.selection)) state.duplicateBlock(id);
    });
    root.querySelector('[data-action="delete"]').addEventListener("click", () => state.deleteSelected());
    root.querySelector('[data-action="group"]').addEventListener("click", () => state.groupSelected());
    root.querySelector('[data-action="ungroup"]').addEventListener("click", () => {
      for (const id of state.selection) state.ungroupBlock(id);
    });
    root.querySelector('[data-action="play"]').addEventListener("click", () => this.transport.play());
    root.querySelector('[data-action="stop"]').addEventListener("click", () => this.transport.stop());

    root.addEventListener("pointerdown", (e) => {
      if (e.target === root) this.close();
    });
  }
}
