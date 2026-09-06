import os
import sys

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PACK_ROOT = os.path.dirname(_TESTS_DIR)               # .../custom_nodes/msch-slideshow-forge
_CUSTOM_NODES_DIR = os.path.dirname(_PACK_ROOT)         # .../custom_nodes
_COMFYUI_ROOT = os.path.dirname(_CUSTOM_NODES_DIR)       # .../ComfyUI

for path in (_PACK_ROOT, _COMFYUI_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)
