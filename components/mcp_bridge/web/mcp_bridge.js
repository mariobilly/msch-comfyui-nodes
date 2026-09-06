import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

function activeGraphCandidates() {
    const candidates = [];
    if (app.canvas?.graph) candidates.push(app.canvas.graph);
    if (app.graph) candidates.push(app.graph);
    return candidates;
}

function nodesOf(graph) {
    if (!graph) return [];
    if (Array.isArray(graph._nodes)) return graph._nodes;
    if (Array.isArray(graph.nodes)) return graph.nodes;
    if (graph._nodes_by_id) return Object.values(graph._nodes_by_id);
    return [];
}

function findNodeById(nodeId) {
    for (const graph of activeGraphCandidates()) {
        if (typeof graph.getNodeById === "function") {
            const n = graph.getNodeById(nodeId);
            if (n) return n;
        }
        const found = nodesOf(graph).find((n) => String(n.id) === String(nodeId));
        if (found) return found;
    }
    return null;
}

api.addEventListener("mcp_bridge.set_widget", (event) => {
    try {
        const { node_id, widget_name, value } = event.detail;
        const node = findNodeById(node_id);
        if (!node) {
            console.warn("[mcp_bridge] node not found:", node_id);
            return;
        }
        const w = node.widgets?.find((w) => w.name === widget_name);
        if (!w) {
            console.warn("[mcp_bridge] widget not found:", widget_name, "on node", node_id);
            return;
        }
        w.value = value;
        node.onWidgetChanged?.(w.name, value, w.value, w);
        app.graph.setDirtyCanvas(true, true);
        app.canvas?.setDirty?.(true, true);
    } catch (e) {
        console.error("[mcp_bridge] set_widget handler error:", e);
    }
});

api.addEventListener("mcp_bridge.set_mode", (event) => {
    try {
        const { node_id, mode } = event.detail;
        const node = findNodeById(node_id);
        if (!node) {
            console.warn("[mcp_bridge] node not found:", node_id);
            return;
        }
        node.mode = mode;
        app.graph.setDirtyCanvas(true, true);
        app.canvas?.setDirty?.(true, true);
    } catch (e) {
        console.error("[mcp_bridge] set_mode handler error:", e);
    }
});

function snapshotGraph() {
    try {
        const candidates = activeGraphCandidates();
        for (const graph of candidates) {
            const nodes = nodesOf(graph);
            if (nodes.length > 0) {
                return nodes.map((n) => ({
                    id: n.id,
                    type: n.type,
                    title: n.title,
                    mode: n.mode,
                    widgets: (n.widgets || []).map((w) => ({ name: w.name, value: w.value })),
                }));
            }
        }
        // Every candidate graph is genuinely empty - return the last one's (empty) mapping.
        return nodesOf(candidates[0]).map((n) => ({
            id: n.id,
            type: n.type,
            title: n.title,
            widgets: (n.widgets || []).map((w) => ({ name: w.name, value: w.value })),
        }));
    } catch (e) {
        console.error("[mcp_bridge] snapshotGraph error:", e);
        return [];
    }
}

let lastSnapshotJson = "";
setInterval(() => {
    const snap = snapshotGraph();
    const json = JSON.stringify(snap);
    if (json !== lastSnapshotJson) {
        lastSnapshotJson = json;
        api.fetchApi("/mcp_bridge/graph_data", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: json,
        });
    }
}, 2000);
