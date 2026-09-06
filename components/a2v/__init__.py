"""ComfyUI entry point for the MschA2V custom node pack.

Aggregates NODE_CLASS_MAPPINGS/NODE_DISPLAY_NAME_MAPPINGS from mscha2v/nodes/*,
registers the sequencer's server routes, and points ComfyUI at the frontend
in web/.

Everything below is wrapped in try/except: pytest's collection machinery
sometimes imports a rootdir __init__.py as a bare file with no resolved
parent package (breaking this file's own relative imports) when it happens
to sit above the tests/ directory, entirely independent of whether ComfyUI
itself is installed. Guarding here means that quirk -- and a genuinely
missing/broken ComfyUI environment -- both degrade to an empty node
registration instead of blocking `python -m pytest` against mscha2v/core.
"""

from __future__ import annotations

import logging

NODE_CLASS_MAPPINGS: dict = {}
NODE_DISPLAY_NAME_MAPPINGS: dict = {}
WEB_DIRECTORY = "./web"

try:
    from .mscha2v.nodes.audio_nodes import NODE_CLASS_MAPPINGS as _AUDIO_NODES
    from .mscha2v.nodes.audio_nodes import NODE_DISPLAY_NAME_MAPPINGS as _AUDIO_NAMES
    from .mscha2v.nodes.beat_ksampler import NODE_CLASS_MAPPINGS as _KSAMPLER_NODES
    from .mscha2v.nodes.beat_ksampler import NODE_DISPLAY_NAME_MAPPINGS as _KSAMPLER_NAMES
    from .mscha2v.nodes.pixel_upscale import NODE_CLASS_MAPPINGS as _UPSCALE_NODES
    from .mscha2v.nodes.pixel_upscale import NODE_DISPLAY_NAME_MAPPINGS as _UPSCALE_NAMES
    from .mscha2v.nodes.sequencer_node import NODE_CLASS_MAPPINGS as _SEQUENCER_NODES
    from .mscha2v.nodes.sequencer_node import NODE_DISPLAY_NAME_MAPPINGS as _SEQUENCER_NAMES
    from .mscha2v.nodes.shot_assembler import NODE_CLASS_MAPPINGS as _ASSEMBLER_NODES
    from .mscha2v.nodes.shot_assembler import NODE_DISPLAY_NAME_MAPPINGS as _ASSEMBLER_NAMES
    from .mscha2v.nodes.shot_planner import NODE_CLASS_MAPPINGS as _PLANNER_NODES
    from .mscha2v.nodes.shot_planner import NODE_DISPLAY_NAME_MAPPINGS as _PLANNER_NAMES

    for _mapping in (_SEQUENCER_NODES, _AUDIO_NODES, _PLANNER_NODES, _KSAMPLER_NODES, _ASSEMBLER_NODES, _UPSCALE_NODES):
        NODE_CLASS_MAPPINGS.update(_mapping)
    for _names in (_SEQUENCER_NAMES, _AUDIO_NAMES, _PLANNER_NAMES, _KSAMPLER_NAMES, _ASSEMBLER_NAMES, _UPSCALE_NAMES):
        NODE_DISPLAY_NAME_MAPPINGS.update(_names)

    from .mscha2v.server import routes as _routes  # noqa: F401  (import registers routes as a side effect)
except Exception as exc:  # pragma: no cover - depends on a running ComfyUI environment
    logging.getLogger(__name__).warning("MschA2V: node/route registration skipped (%s)", exc)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
