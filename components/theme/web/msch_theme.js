// msch-theme -- Mario Signature Palette for every msch-* node pack.
//
//   Matte Carbon   #0B0D0E   node body           (60% shadow)
//   Steel Sea      #344B5C   title bar           (30% material + atmosphere)
//   Espresso       #56382D   bypassed body
//   Tungsten Ochre #C58A32   muted title
//   Aged Bone      #E8E0CF   title text
//   Acid Signal    #C7F432   one thin accent line (10% signal)
//
// A node is themed when its python_module is custom_nodes.msch-<anything>,
// so any future msch- pack picks this up automatically.

import { app } from "../../../scripts/app.js";

const PALETTE = {
    carbon: "#0B0D0E",
    bone: "#E8E0CF",
    steel: "#344B5C",
    espresso: "#56382D",
    ochre: "#C58A32",
    acid: "#C7F432",
};

function isMschNode(nodeData) {
    const mod = String(nodeData?.python_module || "");
    if (/(^|\.)msch-/i.test(mod)) return true;
    const name = String(nodeData?.name || "");
    return /^(msch|mario)/i.test(name);
}

app.registerExtension({
    name: "msch.theme",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!isMschNode(nodeData)) return;

        nodeType.title_text_color = PALETTE.bone;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);
            this.color = PALETTE.steel;
            this.bgcolor = PALETTE.carbon;
            return r;
        };

        const onDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            const r = onDrawForeground?.apply(this, arguments);
            if (this.flags?.collapsed) return r;
            // One electric interruption: a hairline of Acid Signal between title and body.
            ctx.save();
            ctx.fillStyle = PALETTE.acid;
            ctx.fillRect(0, -1, this.size[0], 2);
            ctx.restore();
            return r;
        };
    },
});
