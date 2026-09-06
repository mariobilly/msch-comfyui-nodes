# Local browser bridge

This package exposes local HTTP routes and relays editing events to a connected ComfyUI browser. It adds no executable graph nodes and does not implement a complete MCP server.

| Route | Request | Behavior |
|---|---|---|
| `POST /mcp_bridge/set_widget` | `node_id`, `widget_name`, `value` | Sends an event to the browser to change a matching widget. |
| `POST /mcp_bridge/set_mode` | `node_id`, `mode` | Sends an event to change a node's execution mode. |
| `POST /mcp_bridge/graph_data` | Array of node snapshots | Stores the latest browser snapshot in memory. |
| `GET /mcp_bridge/graph` | None | Returns `nodes` and snapshot `age_seconds`. |

Example read:

```bash
curl http://127.0.0.1:8188/mcp_bridge/graph
```

Example edit, using a node ID and widget name from the returned graph:

```bash
curl -X POST http://127.0.0.1:8188/mcp_bridge/set_widget -H "Content-Type: application/json" -d '{"node_id":1,"widget_name":"filename_prefix","value":"demo"}'
```

`ok: true` acknowledges the server event; it does not prove that a browser found the node or applied the change. Inspect the refreshed graph/browser to confirm the effect. Snapshots are shared in server memory, so multiple browser tabs can replace the stored snapshot. These routes inherit access to your ComfyUI server and add no authentication of their own.

Restart ComfyUI and keep the editor open after installing. The examples describe the local HTTP surface; connecting an external MCP client requires an adapter that calls it.
