"""ComfyUI-WarpWiggle — warp/wiggle (TimeSlice-style) transition + HUD overlay."""

from .warp_wiggle import WarpWiggleTransition
from .warp_stylize import WarpWiggleStylize
from .hud_overlay import HUDOverlay

NODE_CLASS_MAPPINGS = {
    "WarpWiggleTransition": WarpWiggleTransition,
    "WarpWiggleStylize": WarpWiggleStylize,
    "HUDOverlay": HUDOverlay,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WarpWiggleTransition": "WarpWiggle Transition",
    "WarpWiggleStylize": "WarpWiggle Stylize (1 clip)",
    "HUDOverlay": "HUD Overlay",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
