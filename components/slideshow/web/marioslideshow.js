import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { editHeadlines } from "./headline_editor.js";

function mediaURL(file) {
    return api.apiURL(`/view?${new URLSearchParams(file)}`);
}

function message(text) {
    app.extensionManager.toast.add({ severity: "error", summary: "marioslideshow", detail: text, life: 8000 });
}

function addUploads(node, fieldName) {
    let uploading = false;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff";
    input.multiple = true;
    const button = node.addWidget("button", "Upload images", null, () => {
        if (!uploading) input.click();
    }, { serialize: false });
    input.addEventListener("change", async () => {
        const files = [...(input.files || [])];
        if (!files.length) return;
        if (files.length > 200) {
            message("Select up to 200 images.");
            input.value = "";
            return;
        }
        uploading = true;
        const subfolder = `marioslideshow/${crypto.randomUUID()}`;
        let uploadedFolder = null;
        try {
            for (let index = 0; index < files.length; index++) {
                button.name = `Uploading ${index + 1} / ${files.length}`;
                node.setDirtyCanvas(true);
                const file = files[index];
                const safeName = `${String(index + 1).padStart(4, "0")}-${file.name.replace(/[^a-zA-Z0-9._-]/g, "_")}`;
                const body = new FormData();
                body.append("image", file, safeName);
                body.append("subfolder", subfolder);
                body.append("type", "input");
                const response = await api.fetchApi("/upload/image", { method: "POST", body });
                if (!response.ok) throw new Error(`Upload failed for ${file.name} (${response.status}).`);
                const result = await response.json();
                uploadedFolder = result.subfolder;
            }
            const widget = node.widgets.find((w) => w.name === fieldName);
            widget.value = uploadedFolder;
            widget.callback?.(uploadedFolder);
            const limit = node.widgets.find((w) => w.name === "max_images");
            if (limit) limit.value = Math.max(limit.value, files.length);
            button.name = `Upload images (${files.length} loaded)`;
        } catch (error) {
            button.name = "Upload images";
            message(error.message);
        } finally {
            uploading = false;
            input.value = "";
            node.setDirtyCanvas(true, true);
        }
    });
    const originalRemoved = node.onRemoved;
    node.onRemoved = function (...args) {
        input.remove();
        return originalRemoved?.apply(this, args);
    };
}

function addPreview(node) {
    const container = document.createElement("div");
    container.className = "marioslideshow-preview";
    Object.assign(container.style, {
        width: "100%", display: "none", overflow: "hidden", background: "#141416", borderRadius: "4px",
    });
    const video = document.createElement("video");
    video.controls = true;
    video.loop = true;
    video.playsInline = true;
    video.preload = "metadata";
    Object.assign(video.style, { width: "100%", display: "block", objectFit: "contain", background: "#111113" });
    const download = document.createElement("a");
    download.textContent = "Download MP4";
    download.download = "marioslideshow.mp4";
    Object.assign(download.style, { color: "#dfff40", display: "block", padding: "8px 10px", font: "12px sans-serif" });
    container.append(video, download);
    for (const event of ["pointerdown", "pointermove", "pointerup", "wheel"])
        container.addEventListener(event, (e) => e.stopPropagation());
    const widget = node.addDOMWidget("mario_preview", "mario_video", container, {
        serialize: false, hideOnZoom: false,
    });
    let visible = false;
    let aspectRatio = 16 / 9;
    widget.computeSize = function (width) {
        const height = visible ? Math.min(420, (node.size[0] - 20) / aspectRatio) + 34 : 0;
        this.computedHeight = height;
        container.style.height = `${height}px`;
        video.style.height = `${Math.max(0, height - 34)}px`;
        return [Math.max(400, width), height];
    };
    widget.serializeValue = () => undefined;
    video.addEventListener("loadedmetadata", () => {
        node.marioDuration = video.duration;
        aspectRatio = video.videoWidth / video.videoHeight;
        node.setSize([Math.max(400, node.size[0]), node.computeSize()[1]]);
        node.setDirtyCanvas(true, true);
    });
    const original = node.onExecuted;
    node.onExecuted = function (result) {
        original?.apply(this, arguments);
        const file = result?.mario_video?.[0];
        if (!file) return;
        const url = mediaURL(file);
        video.src = url;
        const poster = result?.mario_poster?.[0];
        if (poster) video.poster = this.marioPosterURL = mediaURL(poster);
        download.href = url;
        download.download = file.filename;
        visible = true;
        container.style.display = "block";
        this.setSize([Math.max(400, this.size[0]), this.computeSize()[1]]);
        this.setDirtyCanvas(true, true);
    };
    const originalRemoved = node.onRemoved;
    node.onRemoved = function (...args) {
        video.pause();
        video.removeAttribute("src");
        video.load();
        container.remove();
        return originalRemoved?.apply(this, args);
    };
}

app.registerExtension({
    name: "marioslideshow.controls",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!["marioslideshow", "MarioSlideshowLoadImages", "MarioBeatAnalyzer", "MarioSubjectFramer",
              "MarioSlideshowDirector", "MarioSlideshowRenderer"].includes(nodeData.name)) return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = original?.apply(this, arguments);
            this.color = "#32382b";
            this.bgcolor = "#202221";
            const seedControl = this.widgets.find((widget) => widget.name === "control_after_generate");
            if (seedControl) seedControl.value = "fixed";
            if (["marioslideshow", "MarioSlideshowRenderer"].includes(nodeData.name)) {
                addUploads(this, "image_folder");
                addPreview(this);
                this.addWidget("button", "Edit headlines", null, () => editHeadlines(this, message), {serialize:false});
                const onConfigure = this.onConfigure;
                this.onConfigure = function () {
                    onConfigure?.apply(this, arguments);
                    for (const name of ["show_counter", "show_progress", "show_headlines"]) {
                        const widget = this.widgets.find(w => w.name === name);
                        if (typeof widget.value !== "boolean") widget.value = true;
                    }
                    const layers = this.widgets.find(w => w.name === "headline_layers");
                    if (typeof layers.value !== "string") layers.value = "";
                };
            } else if (nodeData.name === "MarioSlideshowLoadImages") {
                addUploads(this, "directory");
            }
            if (nodeData.name === "MarioSlideshowDirector") {
                let generatedPlan = "";
                const timeline = this.widgets.find(w => w.name === "timeline_json_in");
                const preset = this.widgets.find(w => w.name === "preset");
                const presetChanged = preset.callback;
                preset.callback = function (...args) {
                    presetChanged?.apply(this, args);
                    if (timeline.value?.trim()) app.extensionManager.toast.add({
                        severity: "warn", summary: "Custom plan active",
                        detail: "The saved timeline overrides the preset. Use 'Use preset / clear custom plan' to regenerate.", life: 10000,
                    });
                };
                const onExecuted = this.onExecuted;
                this.onExecuted = function (result) {
                    onExecuted?.apply(this, arguments);
                    generatedPlan = result?.mario_plan_json?.[0] || generatedPlan;
                };
                this.addWidget("button", "Edit generated plan", null, () => {
                    if (!generatedPlan) return message("Run the connected workflow once to generate a shot plan.");
                    const widget = this.widgets.find((w) => w.name === "timeline_json_in");
                    widget.value = generatedPlan;
                    widget.callback?.(generatedPlan);
                    this.setDirtyCanvas(true, true);
                }, { serialize: false });
                this.addWidget("button", "Use preset / clear custom plan", null, () => {
                    if (timeline.value?.trim() && !window.confirm("Clear the custom timeline and use the Director preset on the next run?")) return;
                    timeline.value = "";
                    timeline.callback?.("");
                    this.setDirtyCanvas(true, true);
                }, { serialize: false });
            }
            this.setSize([Math.max(400, this.size[0]), this.computeSize()[1]]);
            return result;
        };
    },
});
