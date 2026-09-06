// Per-block editor: a horizontal row of numeric fields (start/end frame,
// duration, fades, crossfade, seed) followed by large prompt/negative
// textareas underneath -- laid out full-width below the timeline rather
// than as a stacked right-hand sidebar form.

export class InspectorView {
  constructor(container, state) {
    this.container = container;
    this.state = state;
    this.focusedId = null;
    this._unsubscribe = state.subscribe(() => this.render());
    this.render();
  }

  destroy() {
    this._unsubscribe();
  }

  inspect(id) {
    this.focusedId = id;
    this.render();
  }

  _numberField(row, block, label, key, opts = {}) {
    const wrap = document.createElement("label");
    wrap.className = "mscha2v-field-col";
    const span = document.createElement("span");
    span.textContent = label;
    const input = document.createElement("input");
    input.type = "number";
    input.value = block[key] ?? 0;
    input.readOnly = !!opts.readOnly;
    if (opts.readOnly) input.tabIndex = -1;
    input.min = String(opts.min ?? 0);
    input.step = String(opts.step ?? 1);
    if (!opts.readOnly) {
      input.addEventListener("change", () => {
        const val = Number(input.value);
        this.state.updateBlock(block.id, { [key]: Number.isFinite(val) ? val : 0 });
      });
    }
    wrap.appendChild(span);
    wrap.appendChild(input);
    row.appendChild(wrap);
  }

  render() {
    const container = this.container;
    container.innerHTML = "";
    const block = this.state.blocks.find((b) => b.id === this.focusedId);
    if (!block) {
      const empty = document.createElement("div");
      empty.className = "mscha2v-inspector-empty";
      empty.textContent = "Select a prompt block above to edit it.";
      container.appendChild(empty);
      return;
    }

    const fps = this.state.fps || 24;
    const frameCount = block.end_frame - block.start_frame;

    const row = document.createElement("div");
    row.className = "mscha2v-fields-row";
    container.appendChild(row);

    this._numberField(row, block, "Start frame", "start_frame", { readOnly: true });
    this._numberField(row, block, "End frame", "end_frame", { readOnly: true });

    const durationWrap = document.createElement("div");
    durationWrap.className = "mscha2v-field-col";
    const durationLabel = document.createElement("span");
    durationLabel.textContent = "Duration";
    const durationValue = document.createElement("div");
    durationValue.className = "mscha2v-readout-inline";
    durationValue.textContent = `${frameCount}f / ${(frameCount / fps).toFixed(2)}s`;
    durationWrap.appendChild(durationLabel);
    durationWrap.appendChild(durationValue);
    row.appendChild(durationWrap);

    this._numberField(row, block, "Fade in frames", "fade_in_frames");
    this._numberField(row, block, "Fade out frames", "fade_out_frames");
    this._numberField(row, block, "Crossfade frames", "crossfade_frames");

    const seedWrap = document.createElement("label");
    seedWrap.className = "mscha2v-field-col";
    const seedLabel = document.createElement("span");
    seedLabel.textContent = "Seed";
    const seedInput = document.createElement("input");
    seedInput.type = "number";
    seedInput.placeholder = "auto";
    seedInput.value = block.seed ?? "";
    seedInput.addEventListener("change", () => {
      const raw = seedInput.value.trim();
      this.state.updateBlock(block.id, { seed: raw === "" ? null : Number(raw) });
    });
    seedWrap.appendChild(seedLabel);
    seedWrap.appendChild(seedInput);
    row.appendChild(seedWrap);

    const groupWrap = document.createElement("div");
    groupWrap.className = "mscha2v-field-col mscha2v-field-group-readout";
    const groupLabel = document.createElement("span");
    groupLabel.textContent = "Group";
    const groupValue = document.createElement("div");
    groupValue.className = "mscha2v-readout-inline";
    groupValue.textContent = block.group_id || "—";
    groupWrap.appendChild(groupLabel);
    groupWrap.appendChild(groupValue);
    row.appendChild(groupWrap);

    const promptArea = document.createElement("textarea");
    promptArea.className = "mscha2v-prompt-main mono";
    promptArea.placeholder = "Describe what should happen during this shot...";
    promptArea.value = block.prompt;
    promptArea.spellcheck = false;
    promptArea.addEventListener("input", () => this.state.updateBlock(block.id, { prompt: promptArea.value }));
    container.appendChild(promptArea);

    const negArea = document.createElement("textarea");
    negArea.className = "mscha2v-prompt-negative mono";
    negArea.placeholder = "Negative prompt (optional)...";
    negArea.value = block.negative;
    negArea.spellcheck = false;
    negArea.addEventListener("input", () => this.state.updateBlock(block.id, { negative: negArea.value }));
    container.appendChild(negArea);
  }
}
