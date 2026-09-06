from .nodes import MarioTyport
from . import audio_routes

NODE_CLASS_MAPPINGS = {"MarioTyport": MarioTyport}
NODE_DISPLAY_NAME_MAPPINGS = {"MarioTyport": "mariotyport"}
WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
