import json

from ..core.render_engine import assemble_timeline


class GPUMotionRenderer:
    CATEGORY = "SlideshowForge"
    FUNCTION = "render"
    RETURN_TYPES = ("IMAGE",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "timeline_json": ("STRING", {"forceInput": True}),
                "fps": ("INT", {"default": 30, "min": 1, "max": 120}),
            },
            "optional": {
                "render_chunk_frames": ("INT", {"default": 64, "min": 8, "max": 512}),
                "precision": (["fp16", "fp32"], {"default": "fp16"}),
                "device": (["auto", "cuda", "cpu"], {"default": "auto"}),
                "max_output_bytes_gb": ("FLOAT", {"default": 8.0, "min": 0.5, "max": 256.0}),
            },
        }

    def render(
        self,
        images,
        timeline_json,
        fps,
        render_chunk_frames=64,
        precision="fp16",
        device="auto",
        max_output_bytes_gb=8.0,
    ):
        timeline = json.loads(timeline_json)
        frames = assemble_timeline(
            images_nhwc=images,
            timeline=timeline,
            fps=fps,
            render_chunk_frames=render_chunk_frames,
            precision=precision,
            device=device,
            max_output_bytes_gb=max_output_bytes_gb,
        )
        return (frames,)
