import { app } from "../../../scripts/app.js";

// Turn the LyricSyncPalette node's "color_*" string widgets into clickable
// colour swatches. Clicking opens the browser's native colour picker, which on
// Windows Chrome/Edge includes an eyedropper ("pick screen colour"). Falls back
// gracefully to a normal text field if anything here fails — the value is always
// just a #hex string the Python node reads.

function openNativePicker(node, widget) {
  const input = document.createElement("input");
  input.type = "color";
  try { input.value = (widget.value || "#ffffff").slice(0, 7); } catch (e) {}
  input.style.position = "fixed";
  input.style.left = "-9999px";
  input.style.top = "0px";
  document.body.appendChild(input);
  const sync = () => {
    widget.value = (input.value || "#ffffff").toUpperCase();
    node.setDirtyCanvas(true, true);
  };
  input.addEventListener("input", sync);
  input.addEventListener("change", () => {
    sync();
    if (input.parentNode) input.parentNode.removeChild(input);
  });
  input.click();
}

function enhance(node, widget) {
  widget.computeSize = function (width) { return [width, 22]; };

  widget.draw = function (ctx, n, width, y, height) {
    const margin = 15;
    const sw = 26;
    const h = 18;
    const col = (this.value || "#000000").toString();
    // swatch
    ctx.fillStyle = col;
    ctx.fillRect(margin, y + 1, sw, h);
    ctx.strokeStyle = "#0008";
    ctx.strokeRect(margin, y + 1, sw, h);
    // label + value
    ctx.fillStyle = "#DDD";
    ctx.font = "12px monospace";
    ctx.textAlign = "left";
    ctx.fillText(`${this.name}  ${col.toUpperCase()}`, margin + sw + 8, y + 14);
  };

  widget.mouse = function (event, pos, n) {
    if (event.type === "pointerdown" || event.type === "mousedown") {
      openNativePicker(n, this);
      return true;
    }
    return false;
  };
}

app.registerExtension({
  name: "LyricSync.PaletteColorPicker",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== "LyricSyncPalette") return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
      for (const w of this.widgets || []) {
        if (w && typeof w.name === "string" && w.name.startsWith("color_")) {
          try { enhance(this, w); } catch (e) { console.warn("LyricSync color widget:", e); }
        }
      }
      return r;
    };
  },
});
