"""Generic Ken-Burns frame-stack renderer.

Every motion "type" in the timeline JSON (zoom_in, pan_left, rotate_slow, ...)
is rendered by this single function -- it only reads the six numeric params
(start/end scale, pan_x, pan_y, rotation) and never branches on the type
label. All tensors here are channel-first (N,3,H,W); callers convert from
ComfyUI's channel-last (N,H,W,3) convention at the render_engine boundary.
"""

import math

import torch
import torch.nn.functional as F


def easing_linear(t):
    return t


def easing_ease_in(t):
    return t * t


def easing_ease_out(t):
    return 1.0 - (1.0 - t) * (1.0 - t)


def easing_ease_in_out(t):
    return t * t * (3.0 - 2.0 * t)


EASING_FUNCTIONS = {
    "linear": easing_linear,
    "ease_in": easing_ease_in,
    "ease_out": easing_ease_out,
    "ease_in_out": easing_ease_in_out,
}


def get_easing_fn(name: str):
    if name not in EASING_FUNCTIONS:
        raise ValueError(f"Unknown easing: {name!r}. Available: {list(EASING_FUNCTIONS.keys())}")
    return EASING_FUNCTIONS[name]


def render_kenburns_segment(
    base_chw: torch.Tensor,
    params: dict,
    frame_count: int,
    easing_fn,
    device,
    dtype,
    t_start: float = 0.0,
    t_end: float = 1.0,
    num_frames: int = None,
) -> torch.Tensor:
    """Render a single image's motion as a (num_frames, 3, H, W) frame stack.

    base_chw: (1, 3, H, W) tensor, already canvas-fitted, on `device`/`dtype`.
    params: the segment's motion.params dict (start_scale, end_scale,
        pan_x_start/end, pan_y_start/end, rotation_deg_start/end).

    `frame_count` is the segment's TOTAL frame count (defines the 0..1 time
    grid); `t_start`/`t_end`/`num_frames` let a caller render only a
    sub-range of that grid (for VRAM-bounded chunked rendering of long
    segments) while producing bit-identical frames to a full-segment render
    at the same indices. Defaults render the whole segment in one call.
    """
    if frame_count < 1:
        raise ValueError("frame_count must be >= 1")
    if num_frames is None:
        num_frames = frame_count
    if num_frames < 1:
        raise ValueError("num_frames must be >= 1")

    _, _, H, W = base_chw.shape

    t = torch.linspace(t_start, t_end, num_frames, device=device, dtype=dtype)
    t_eased = easing_fn(t)

    start_scale = float(params["start_scale"])
    end_scale = float(params["end_scale"])
    scale_t = start_scale + (end_scale - start_scale) * t_eased
    scale_t = torch.clamp(scale_t, min=1e-3)

    pan_x_start = float(params["pan_x_start"])
    pan_x_end = float(params["pan_x_end"])
    pan_y_start = float(params["pan_y_start"])
    pan_y_end = float(params["pan_y_end"])
    cx_t = pan_x_start + (pan_x_end - pan_x_start) * t_eased
    cy_t = pan_y_start + (pan_y_end - pan_y_start) * t_eased

    # Geometric safety clamp: a zoom of scale_t samples a window of
    # half-width 1/scale_t in normalized [-1,1] coords, so the center can
    # move by at most 1 - 1/scale_t before an edge exceeds source bounds.
    max_offset = torch.clamp(1.0 - 1.0 / scale_t, min=0.0)
    cx_t = torch.clamp(cx_t, min=-1.0, max=1.0)
    cx_t = torch.minimum(torch.maximum(cx_t, -max_offset), max_offset)
    cy_t = torch.minimum(torch.maximum(cy_t, -max_offset), max_offset)

    rot_start = math.radians(float(params["rotation_deg_start"]))
    rot_end = math.radians(float(params["rotation_deg_end"]))
    rot_t = rot_start + (rot_end - rot_start) * t_eased

    cos_t = torch.cos(rot_t) / scale_t
    sin_t = torch.sin(rot_t) / scale_t

    theta = torch.zeros((num_frames, 2, 3), device=device, dtype=dtype)
    theta[:, 0, 0] = cos_t
    theta[:, 0, 1] = -sin_t
    theta[:, 0, 2] = cx_t
    theta[:, 1, 0] = sin_t
    theta[:, 1, 1] = cos_t
    theta[:, 1, 2] = cy_t

    grid = F.affine_grid(theta, size=(num_frames, 3, H, W), align_corners=False)
    frames = F.grid_sample(
        base_chw.expand(num_frames, -1, -1, -1),
        grid,
        mode="bilinear",
        padding_mode="reflection",
        align_corners=False,
    )
    return frames
