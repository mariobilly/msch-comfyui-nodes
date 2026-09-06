"""MSCH Nodes: one ComfyUI package for the complete collection."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ._loader import load_components

_root = Path(__file__).resolve().parent
_definitions = json.loads((_root / "components.json").read_text(encoding="utf-8"))
try:
    import folder_paths
    _legacy_roots = [Path(path) for path in folder_paths.get_folder_paths("custom_nodes")]
except ImportError:
    _legacy_roots = []

NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS, LOADED_COMPONENTS, SKIPPED_COMPONENTS, LOAD_ERRORS = (
    load_components(__package__, _definitions, _legacy_roots)
)
WEB_DIRECTORY = "./web"

try:
    from aiohttp import web
    from server import PromptServer

    _scripts = []
    for _component in LOADED_COMPONENTS:
        if not _component.get("web_entry"):
            continue
        _prefix = f"/msch_nodes/assets/{_component['module']}"
        _directory = _root / "components" / _component["module"] / "web"
        PromptServer.instance.routes.static(_prefix, str(_directory), show_index=False)
        _scripts.append(f"{_prefix}/{_component['web_entry']}")

    @PromptServer.instance.routes.get("/msch_nodes/components")
    async def msch_components(request):
        return web.json_response({"scripts": _scripts, "loaded": [c["module"] for c in LOADED_COMPONENTS],
                                  "skipped_legacy": list(SKIPPED_COMPONENTS), "errors": LOAD_ERRORS})
except ImportError:
    logging.getLogger("msch_nodes").debug("MSCH Nodes: web registration requires a ComfyUI server.")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
