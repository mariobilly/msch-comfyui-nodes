import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { openSequencerModal } from "./sequencer/modal.js";

const SEQUENCER_NODE = "MschA2V_BeatPromptSequencer";

function ensureStylesheet() {
  if (document.querySelector('link[data-mscha2v-styles]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = new URL("./sequencer/styles.css", import.meta.url).href;
  link.setAttribute("data-mscha2v-styles", "1");
  document.head.appendChild(link);
}
ensureStylesheet();

app.registerExtension({
  name: "MschA2V.Sequencer",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== SEQUENCER_NODE) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

      const scheduleWidget = this.widgets?.find((w) => w.name === "schedule_json");
      if (scheduleWidget) {
        // Keep it in the serialized workflow, but don't render it on the canvas.
        scheduleWidget.computeSize = () => [0, -4];
        if (scheduleWidget.inputEl) scheduleWidget.inputEl.style.display = "none";
      }

      const audioPathWidget = this.widgets?.find((w) => w.name === "audio_path");
      this._mscha2vRefreshFileList = async () => {
        if (!audioPathWidget) return;
        try {
          const res = await api.fetchApi("/mscha2v/files?dir=input&ext=audio");
          const files = await res.json();
          if (Array.isArray(files)) {
            const options = files.map((f) => f.path);
            audioPathWidget.options = audioPathWidget.options || {};
            audioPathWidget.options.values = options;
          }
        } catch (err) {
          console.warn("MschA2V: failed to list input audio files", err);
        }
      };
      this._mscha2vRefreshFileList();

      this.addWidget("button", "Open Sequencer", null, () => {
        openSequencerModal({
          node: this,
          audioPathWidget,
          scheduleWidget,
          onDone: () => {
            this.setDirtyCanvas(true, true);
          },
        });
      });

      return result;
    };
  },
});
