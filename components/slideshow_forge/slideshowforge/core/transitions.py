"""Transition blending: crossfade / directional & diagonal wipes / blur_dissolve.

All functions take two (k,3,H,W) frame stacks (the outgoing segment's tail
and the incoming segment's head, both already rendered independently) and an
eased progress tensor (k,), and return one blended (k,3,H,W) stack. Boundary
guarantee: progress=0 -> pure A, progress=1 -> pure B, for every function
here (verified by tests/test_transitions.py).
"""

import math

import kornia.filters
import torch

WIPE_DIRECTIONS = {
    "wipe_left": "left",
    "wipe_right": "right",
    "wipe_up": "up",
    "wipe_down": "down",
    "diagonal_wipe_tl": "diagonal_tl",
    "diagonal_wipe_br": "diagonal_br",
}


def crossfade(A: torch.Tensor, B: torch.Tensor, progress: torch.Tensor) -> torch.Tensor:
    alpha = progress.view(-1, 1, 1, 1)
    return alpha * B + (1.0 - alpha) * A


def _direction_field(direction: str, H: int, W: int, device, dtype) -> torch.Tensor:
    x = torch.linspace(0.0, 1.0, W, device=device, dtype=dtype).view(1, 1, 1, W)
    y = torch.linspace(0.0, 1.0, H, device=device, dtype=dtype).view(1, 1, H, 1)

    if direction == "right":
        field = x.expand(1, 1, H, W)
    elif direction == "left":
        field = (1.0 - x).expand(1, 1, H, W)
    elif direction == "down":
        field = y.expand(1, 1, H, W)
    elif direction == "up":
        field = (1.0 - y).expand(1, 1, H, W)
    elif direction == "diagonal_tl":
        field = (x + y) / 2.0
    elif direction == "diagonal_br":
        field = ((1.0 - x) + (1.0 - y)) / 2.0
    else:
        raise ValueError(f"Unknown wipe direction: {direction!r}")

    return field.expand(1, 1, H, W)


def wipe(
    A: torch.Tensor,
    B: torch.Tensor,
    progress: torch.Tensor,
    direction: str,
    feather_px: float,
) -> torch.Tensor:
    k, _, H, W = A.shape
    device, dtype = A.device, A.dtype

    field = _direction_field(direction, H, W, device, dtype)  # (1,1,H,W), range [0,1]
    feather = max(float(feather_px) / max(W, H), 1e-4)

    p = progress.view(k, 1, 1, 1)
    # Boundary domain padded by `feather` on each side so mask is exactly 0
    # at progress=0 and exactly 1 at progress=1 for every pixel.
    boundary = -feather + p * (1.0 + 2.0 * feather)
    mask = torch.clamp((boundary - field) / feather + 0.5, 0.0, 1.0)

    return mask * B + (1.0 - mask) * A


def _kernel_size_for_sigma(sigma: float, max_dim: int) -> int:
    """Odd kernel size for `sigma`, capped so gaussian_blur2d's reflect
    padding never exceeds the frame's own dimensions (which would crash on
    small canvases / thumbnails)."""
    k = max(3, int(2 * round(3.0 * sigma) + 1))
    limit = max(3, 2 * (max_dim - 1) + 1)
    return min(k, limit)


def blur_dissolve(A: torch.Tensor, B: torch.Tensor, progress: torch.Tensor, max_sigma: float) -> torch.Tensor:
    k = A.shape[0]
    blended = crossfade(A, B, progress)

    if max_sigma <= 0:
        return blended

    max_dim = min(A.shape[-2], A.shape[-1])
    frames = []
    for i in range(k):
        t = float(progress[i].item())
        sigma = max(max_sigma * math.sin(math.pi * t), 1e-3)
        ksize = _kernel_size_for_sigma(sigma, max_dim)
        frames.append(kornia.filters.gaussian_blur2d(blended[i:i + 1], (ksize, ksize), (sigma, sigma)))
    return torch.cat(frames, dim=0)


def render_transition(
    A: torch.Tensor,
    B: torch.Tensor,
    transition: dict,
    easing_fn,
) -> torch.Tensor:
    """Dispatch to the right blend function for transition["type"]."""
    k = A.shape[0]
    t = torch.linspace(0.0, 1.0, k, device=A.device, dtype=A.dtype)
    progress = easing_fn(t)

    ttype = transition["type"]
    params = transition.get("params", {})

    if ttype == "crossfade":
        return crossfade(A, B, progress)
    if ttype in WIPE_DIRECTIONS:
        feather_px = params.get("feather_px", 16.0)
        return wipe(A, B, progress, WIPE_DIRECTIONS[ttype], feather_px)
    if ttype == "blur_dissolve":
        max_sigma = params.get("max_sigma", 6.0)
        return blur_dissolve(A, B, progress, max_sigma)
    raise ValueError(f"Unknown or unsupported transition type for rendering: {ttype!r}")
