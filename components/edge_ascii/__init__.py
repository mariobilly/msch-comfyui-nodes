from .nodes import EdgeASCII
from .video_nodes import MschEdgeASCIIVideo

NODE_CLASS_MAPPINGS = {"EdgeASCII": EdgeASCII, "MschEdgeASCIIVideo": MschEdgeASCIIVideo}
NODE_DISPLAY_NAME_MAPPINGS = {"EdgeASCII": "msch-edge-ascii (frames)", "MschEdgeASCIIVideo": "msch-edge-ascii"}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
