import { api } from "../../scripts/api.js";

// Await registration before ComfyUI proceeds to node-definition hooks.
// Only load active components, so legacy installations do not register twice.
const response = await api.fetchApi("/msch_nodes/components");
if (!response.ok) throw new Error(`MSCH Nodes: component discovery failed (${response.status})`);
const components = await response.json();
const results = await Promise.allSettled(
    components.scripts.map((path) => import(api.apiURL(path)))
);
for (let index = 0; index < results.length; index++) {
    if (results[index].status === "rejected") {
        console.error(`MSCH Nodes: ${components.scripts[index]} failed to load`, results[index].reason);
    }
}
if (components.skipped_legacy.length) {
    console.warn("MSCH Nodes: separate installations detected. See MIGRATION.md:", components.skipped_legacy);
}
