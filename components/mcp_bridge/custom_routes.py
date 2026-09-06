import time

import server
from aiohttp import web

_last_graph = {"nodes": [], "stored_at": None}


@server.PromptServer.instance.routes.post("/mcp_bridge/set_widget")
async def mcp_bridge_set_widget(request):
    data = await request.json()
    server.PromptServer.instance.send_sync("mcp_bridge.set_widget", data)
    return web.json_response({"ok": True})


@server.PromptServer.instance.routes.post("/mcp_bridge/set_mode")
async def mcp_bridge_set_mode(request):
    data = await request.json()
    server.PromptServer.instance.send_sync("mcp_bridge.set_mode", data)
    return web.json_response({"ok": True})


@server.PromptServer.instance.routes.post("/mcp_bridge/graph_data")
async def mcp_bridge_graph_data(request):
    data = await request.json()
    _last_graph["nodes"] = data
    _last_graph["stored_at"] = time.time()
    return web.json_response({"ok": True})


@server.PromptServer.instance.routes.get("/mcp_bridge/graph")
async def mcp_bridge_graph(request):
    stored_at = _last_graph["stored_at"]
    age_seconds = (time.time() - stored_at) if stored_at is not None else None
    return web.json_response({"nodes": _last_graph["nodes"], "age_seconds": age_seconds})
