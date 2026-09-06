"""Animate the effect and return a native ComfyUI VIDEO."""

from fractions import Fraction
import math

import torch
import torch.nn.functional as F
from comfy_api.latest import InputImpl, Types
from comfy.model_management import throw_exception_if_processing_interrupted
from comfy.utils import ProgressBar

from .nodes import EdgeASCII


class MschEdgeASCIIVideo:
    CATEGORY = "video/effects"
    FUNCTION = "animate"
    RETURN_TYPES = ("VIDEO",)
    RETURN_NAMES = ("video",)
    DESCRIPTION = "Animate ASCII marks over a photo or process a video with its original FPS and audio. Connect VIDEO to Save Video to export MP4."
    SEARCH_ALIASES = ["msch-edge-ascii", "edge ascii video", "animate ascii"]
    VALIDATE_INPUTS = EdgeASCII.VALIDATE_INPUTS

    @classmethod
    def INPUT_TYPES(cls):
        effect = EdgeASCII.INPUT_TYPES()
        required = {
            "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.01,
                              "tooltip": "Frame rate for a still photo or IMAGE batch. VIDEO input retains its own FPS."}),
            "duration_seconds": ("FLOAT", {"default": 4.0, "min": 0.1, "max": 60.0, "step": 0.1,
                                           "tooltip": "Duration when animating one photo. Existing videos and frame batches retain their length."}),
            "animation": (["flow", "pulse", "none"],),
            "cycles": ("INT", {"default": 1, "min": 1, "max": 32,
                                "tooltip": "Complete animation cycles over the clip; integer cycles loop smoothly on a still photo."}),
            "animation_strength": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.05}),
        }
        required.update({key: value for key, value in effect["required"].items() if key != "image"})
        return {"required": required, "optional": {
            "image": ("IMAGE", {"tooltip": "Connect a single photo to animate, or a batch of video frames. Connect either image or video."}),
            "video": ("VIDEO", {"tooltip": "Connect Load Video; its FPS, frame count and audio are preserved."}),
            "audio": ("AUDIO", {"tooltip": "Optional soundtrack; overrides audio from VIDEO input."}),
            "mask": effect["optional"]["mask"],
        }}

    def animate(self, fps=24.0, duration_seconds=4.0, animation="flow", cycles=1,
                animation_strength=0.85, image=None, video=None, audio=None, mask=None, **effect):
        if (image is None) == (video is None):
            raise ValueError("Connect either image or video, not both.")
        if animation not in ("flow", "pulse", "none"):
            raise ValueError("Unknown animation mode.")
        if not math.isfinite(fps) or fps <= 0 or not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise ValueError("FPS and duration must be positive finite values.")
        frame_rate = Fraction(str(fps)).limit_denominator(100000)
        if video is not None:
            components = video.get_components()
            image = components.images
            frame_rate = components.frame_rate
            if audio is None:
                audio = components.audio
        if image.ndim != 4 or image.shape[-1] != 3 or min(image.shape[:3]) < 1:
            raise ValueError("Expected a nonempty RGB photo or frame batch.")
        is_still = video is None and image.shape[0] == 1
        count = max(1, round(float(frame_rate) * duration_seconds)) if is_still else image.shape[0]
        h, w = image.shape[1:3]
        # H.264 4:2:0 requires even dimensions. Extend the last row/column only.
        output = torch.empty((count, h + h % 2, w + w % 2, 3), dtype=torch.float32, device="cpu")
        cell_size = effect.get("cell_size", 16)
        phase = (torch.arange(h)[:, None] // cell_size + torch.arange(w)[None, :] // cell_size).float() / 12
        renderer = EdgeASCII()
        progress = ProgressBar(count)
        if mask is not None and (mask.ndim not in (2, 3) or (mask.ndim == 3 and mask.shape[0] not in (1, image.shape[0]))):
            raise ValueError("Mask must be a single mask or match the source frame count.")
        styled = base = None
        for index in range(count):
            throw_exception_if_processing_interrupted()
            if index == 0 or not is_still:
                source_index = 0 if is_still else index
                source = image[source_index:source_index + 1].detach().to(device="cpu", dtype=torch.float32)
                selected_mask = mask
                if mask is not None and mask.ndim == 3 and mask.shape[0] > 1:
                    selected_mask = mask[source_index:source_index + 1]
                styled = renderer.apply(source, mask=selected_mask, **effect)[0][0]
                if effect.get("background", "original") == "solid":
                    base = renderer.apply(source, mask=selected_mask, **{**effect, "opacity": 0.0})[0][0]
                else:
                    base = source[0].nan_to_num().clamp(0, 1)
            if animation == "none" or animation_strength == 0:
                frame = styled
            else:
                time = cycles * index / count
                angle = 2 * math.pi * (phase - time if animation == "flow" else -time)
                wave = (0.5 + 0.5 * (torch.cos(angle) if animation == "flow" else math.cos(angle))) ** 2
                gain = 1 - animation_strength + animation_strength * wave
                frame = base + (styled - base) * (gain[..., None] if animation == "flow" else gain)
            if h % 2 or w % 2:
                frame = F.pad(frame.permute(2, 0, 1)[None], (0, w % 2, 0, h % 2), mode="replicate")[0].permute(1, 2, 0)
            output[index].copy_(frame)
            progress.update_absolute(index + 1)
        return (InputImpl.VideoFromComponents(Types.VideoComponents(
            images=output, frame_rate=frame_rate, audio=audio)),)
