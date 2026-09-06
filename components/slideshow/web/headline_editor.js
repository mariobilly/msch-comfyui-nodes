const defaults = () => ({text:"HEADLINE", start:0, end:2, x:8, y:70, width:84, size:8,
    color:"#FFFFFF", align:"left", animation:"fade", enabled:true});

export function editHeadlines(node, reportError) {
    const widget = node.widgets.find(w => w.name === "headline_layers");
    let layers;
    try {
        layers = JSON.parse(widget.value || "[]");
        if (!Array.isArray(layers) || layers.length > 200 || layers.some(l => !l || typeof l !== "object" || Array.isArray(l)))
            throw new Error("Headline layers must be an array of up to 200 objects.");
        layers = layers.map(l => ({...defaults(), ...l}));
        for (const layer of layers) {
            if (Object.entries(defaults()).some(([key,value]) => typeof layer[key] !== typeof value)
                || ["start","end","x","y","width","size"].some(key => !Number.isFinite(layer[key])))
                throw new Error("Headline fields have invalid types. Check the headline_layers JSON.");
        }
    } catch (error) { reportError(error.message); return; }
    const dimensions = name => Number(node.widgets.find(w => w.name === name)?.value);
    const width = dimensions("width") || 1280, height = dimensions("height") || 720;
    let selected = layers.length ? 0 : -1, seconds = 0;
    const dialog = document.createElement("dialog");
    dialog.className = "mario-title-editor";
    dialog.setAttribute("aria-label", "Headline editor");
    dialog.innerHTML = `<style>
        .mario-title-editor{background:#202221;color:#f5f5f5;border:1px solid #666;border-radius:6px;width:min(1000px,94vw);max-height:92vh;padding:18px;box-sizing:border-box;font:14px Arial,sans-serif;letter-spacing:0;overflow:auto}
        .mario-title-editor::backdrop{background:#0009}
        .mario-title-editor *{box-sizing:border-box}
        .mario-title-editor header,.mario-title-editor footer{display:flex;align-items:center;justify-content:space-between;gap:12px}
        .mario-title-editor h2{font-size:18px;margin:0}
        .mario-title-editor .body{display:grid;grid-template-columns:minmax(0,1fr) 250px;gap:18px;margin:16px 0}
        .mario-title-editor .stage{position:relative;width:min(100%,calc(46vh * var(--ratio)));aspect-ratio:var(--ratio);margin:0 auto;background-color:#383c3f;background-size:100% 100%;overflow:hidden;touch-action:none}
        .mario-title-editor .caption{position:absolute;color:white;font-weight:bold;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.15;cursor:move;user-select:none;outline:1px dashed transparent;text-shadow:0 1px 2px #000}
        .mario-title-editor .caption.selected{outline-color:#dfff40}
        .mario-title-editor .scrub{display:flex;gap:8px;align-items:center;margin:12px 0}
        .mario-title-editor .scrub input[type=range]{flex:1;min-width:0}
        .mario-title-editor input,.mario-title-editor textarea,.mario-title-editor select{background:#303433;color:#fff;border:1px solid #747b76;border-radius:3px;padding:5px;max-width:100%;font:13px Arial,sans-serif}
        .mario-title-editor input[type=number]{width:100%}
        .mario-title-editor input[type=color]{width:100%;height:30px;padding:2px}
        .mario-title-editor label{display:flex;flex-direction:column;gap:4px;font-size:12px;min-width:0}
        .mario-title-editor label.check{flex-direction:row;align-items:center}
        .mario-title-editor .fields{display:grid;grid-template-columns:1fr 1fr;gap:10px}
        .mario-title-editor .wide{grid-column:1/-1}
        .mario-title-editor textarea{width:100%;resize:vertical;min-height:68px}
        .mario-title-editor button{background:#414844;color:#fff;border:1px solid #7b887f;border-radius:3px;padding:7px 10px;cursor:pointer;font:13px Arial,sans-serif}
        .mario-title-editor button:disabled{opacity:.4;cursor:default}
        .mario-title-editor .apply{background:#dfff40;color:#171b12;border-color:#dfff40}
        .mario-title-editor .actions{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
        .mario-title-editor .list{width:100%;height:110px}
        .mario-title-editor fieldset{padding:0;border:0;margin:0;min-width:0}
        .mario-title-editor output{min-width:64px;text-align:right;font-variant-numeric:tabular-nums}
        @media(max-width:700px){.mario-title-editor .body{grid-template-columns:1fr}.mario-title-editor{padding:12px}.mario-title-editor .stage{width:min(100%,calc(35vh * var(--ratio)))}}
    </style>
    <header><h2>Headlines</h2><button type="button" data-action="close" aria-label="Close headline editor">Close</button></header>
    <div class="body"><div>
        <div class="stage" aria-label="Headline placement"></div>
        <div class="scrub"><input aria-label="Preview time" type="range" min="0" max="30" step="0.01" value="0"><output>0.00 s</output></div>
        <label class="check"><input type="checkbox" data-photo checked>Last render poster</label>
        <select class="list" size="5" aria-label="Headline layers"></select>
        <div class="actions"><button data-action="add">Add headline</button><button data-action="duplicate">Duplicate</button><button data-action="delete">Delete</button></div>
    </div><fieldset><div class="fields">
        <label class="wide">Text<textarea data-field="text" maxlength="2000"></textarea></label>
        <label>Start (seconds)<input data-field="start" type="number" min="0" max="23999" step="0.01"></label>
        <label>End (seconds)<input data-field="end" type="number" min="0.01" max="24000" step="0.01"></label>
        <label>X (%)<input data-field="x" type="number" min="0" max="99" step="0.1"></label>
        <label>Y (%)<input data-field="y" type="number" min="0" max="99" step="0.1"></label>
        <label>Width (%)<input data-field="width" type="number" min="1" max="100" step="1"></label>
        <label>Size (%)<input data-field="size" type="number" min="1" max="50" step="0.5"></label>
        <label>Color<input data-field="color" type="color"></label>
        <label>Alignment<select data-field="align"><option>left</option><option>center</option><option>right</option></select></label>
        <label>Animation<select data-field="animation"><option>fade</option><option>slide</option><option>none</option></select></label>
        <label class="check"><input data-field="enabled" type="checkbox">Visible</label>
    </div></fieldset></div>
    <footer><span data-count></span><button class="apply" data-action="apply">Apply</button></footer>`;
    const stage = dialog.querySelector(".stage"), list = dialog.querySelector(".list");
    const scrub = dialog.querySelector(".scrub input"), fields = [...dialog.querySelectorAll("[data-field]")];
    stage.style.setProperty("--ratio", width / height);
    const duration = () => Math.max(node.marioDuration || 30, ...layers.map(l => Number(l.end) || 0));
    const updateList = () => {
        list.replaceChildren(...layers.map((layer, index) => {
            const option = document.createElement("option"); option.value = index;
            option.textContent = `${index + 1}. ${layer.enabled ? "" : "[off] "}${layer.text.replace(/\s+/g," ").slice(0,40) || "Untitled"}`;
            return option;
        }));
        list.value = selected;
        dialog.querySelector("[data-count]").textContent = `${layers.length} / 200 headlines`;
        dialog.querySelector('[data-action="add"]').disabled = layers.length >= 200;
        for (const action of ["duplicate", "delete"])
            dialog.querySelector(`[data-action="${action}"]`).disabled = selected < 0 || (action === "duplicate" && layers.length >= 200);
    };
    const draw = () => {
        stage.replaceChildren();
        stage.style.backgroundImage = dialog.querySelector("[data-photo]").checked && node.marioPosterURL ? `url("${node.marioPosterURL}")` : "none";
        for (const [index, layer] of layers.entries()) {
            if (!layer.enabled || seconds < layer.start || seconds >= layer.end) continue;
            const caption = document.createElement("div"); caption.className = `caption${index === selected ? " selected" : ""}`;
            caption.dataset.layer = index; caption.textContent = layer.text;
            Object.assign(caption.style, {left:`${layer.x}%`, top:`${layer.y}%`, width:`${Math.min(layer.width,100-layer.x)}%`,
                fontSize:`${Math.min(stage.clientWidth,stage.clientHeight)*layer.size/100}px`, color:layer.color, textAlign:layer.align});
            stage.append(caption);
            const available = stage.clientHeight * (1-layer.y/100);
            if (caption.scrollHeight > available && available > 0)
                caption.style.fontSize = `${parseFloat(caption.style.fontSize)*available/caption.scrollHeight}px`;
        }
        scrub.max = duration(); scrub.value = seconds;
        dialog.querySelector("output").textContent = `${seconds.toFixed(2)} s`;
    };
    const refresh = () => {
        updateList(); dialog.querySelector("fieldset").disabled = selected < 0;
        if (selected >= 0) for (const field of fields) {
            if (field.type === "checkbox") field.checked = layers[selected][field.dataset.field];
            else field.value = layers[selected][field.dataset.field];
        }
        draw();
    };
    fields.forEach(field => field.addEventListener("input", () => {
        if (selected < 0) return;
        let value = field.type === "checkbox" ? field.checked : field.type === "number" ? Number(field.value) : field.value;
        if (field.type === "number") value = Math.max(Number(field.min), Math.min(Number(field.max), value));
        layers[selected][field.dataset.field] = value;
        updateList(); draw();
    }));
    list.addEventListener("change", () => {
        selected = Number(list.value); seconds = layers[selected].start + Math.min(0.3,(layers[selected].end-layers[selected].start)/2); refresh();
    });
    scrub.addEventListener("input", () => {seconds=Number(scrub.value); draw();});
    dialog.querySelector("[data-photo]").addEventListener("change", draw);
    let drag = null;
    stage.addEventListener("pointerdown", event => {
        const target = event.target.closest("[data-layer]"); if (!target) return;
        selected=Number(target.dataset.layer);
        drag={px:event.clientX,py:event.clientY,x:layers[selected].x,y:layers[selected].y};
        stage.setPointerCapture(event.pointerId); refresh(); event.preventDefault();
    });
    stage.addEventListener("pointermove", event => {
        if (!drag) return;
        layers[selected].x=Math.round(Math.max(0,Math.min(99,drag.x+(event.clientX-drag.px)/stage.clientWidth*100))*10)/10;
        layers[selected].y=Math.round(Math.max(0,Math.min(99,drag.y+(event.clientY-drag.py)/stage.clientHeight*100))*10)/10;
        refresh();
    });
    stage.addEventListener("pointerup", () => {drag=null;});
    stage.addEventListener("pointercancel", () => {drag=null;});
    const observer = new ResizeObserver(draw);
    const close = () => {observer.disconnect(); dialog.close(); dialog.remove();};
    dialog.addEventListener("cancel", event => {event.preventDefault(); close();});
    dialog.addEventListener("keydown", event => event.stopPropagation());
    dialog.addEventListener("click", event => {
        const action = event.target.closest("[data-action]")?.dataset.action;
        if (action === "close") return close();
        if (action === "add" && layers.length < 200) {
            layers.push({...defaults(),start:Math.round(seconds*100)/100,end:Math.min(24000,Math.round((seconds+2)*100)/100)});
            selected=layers.length-1;
        } else if (action === "duplicate" && selected >= 0 && layers.length < 200) {
            layers.push({...layers[selected], y:Math.min(99,layers[selected].y+8)}); selected=layers.length-1;
        } else if (action === "delete" && selected >= 0) {
            layers.splice(selected,1); selected=Math.min(selected,layers.length-1);
        } else if (action === "apply") {
            if (layers.some(l => !Number.isFinite(l.start) || !Number.isFinite(l.end) || l.end <= l.start))
                return reportError("Every headline must end after it starts.");
            widget.value=layers.length ? JSON.stringify(layers,null,2) : "";
            widget.callback?.(widget.value); node.setDirtyCanvas(true,true); close(); return;
        } else return;
        refresh();
    });
    document.body.append(dialog); dialog.showModal(); observer.observe(stage); refresh();
}
