from .director import SlideshowDirector
from .renderer import GPUMotionRenderer

NODE_CLASS_MAPPINGS = {
    "SlideshowForge_Director": SlideshowDirector,
    "SlideshowForge_GPURenderer": GPUMotionRenderer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SlideshowForge_Director": "Slideshow Director",
    "SlideshowForge_GPURenderer": "GPU Motion Renderer",
}
