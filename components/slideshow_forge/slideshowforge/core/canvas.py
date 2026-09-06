"""Per-image canvas fitting: cover / contain_black_bg / contain_blur_bg.

Done once per image (batched), not per frame. All tensors here are
channel-first (N,3,H,W), matching comfy.utils.common_upscale's convention.
"""

import kornia.filters
import torch
import torch.nn.functional as F

import comfy.utils

FIT_MODES = ("cover", "contain_blur_bg", "contain_black_bg")


def _kernel_size_for_sigma(sigma: float, max_dim: int) -> int:
    """Odd kernel size for `sigma`, capped so gaussian_blur2d's reflect
    padding never exceeds the frame's own dimensions (which would crash on
    small canvases / thumbnails)."""
    k = max(3, int(2 * round(3.0 * sigma) + 1))
    limit = max(3, 2 * (max_dim - 1) + 1)
    return min(k, limit)


def cover(images_chw: torch.Tensor, width: int, height: int) -> torch.Tensor:
    return comfy.utils.common_upscale(images_chw, width, height, "lanczos", "center")


def _contain_resize(images_chw: torch.Tensor, width: int, height: int):
    _, _, H, W = images_chw.shape
    aspect_src = W / H
    aspect_dst = width / height
    if aspect_src > aspect_dst:
        new_w, new_h = width, max(1, round(width / aspect_src))
    else:
        new_h, new_w = height, max(1, round(height * aspect_src))
    resized = F.interpolate(images_chw, size=(new_h, new_w), mode="bilinear", align_corners=False)
    return resized, new_w, new_h


def contain_black_bg(images_chw: torch.Tensor, width: int, height: int) -> torch.Tensor:
    resized, new_w, new_h = _contain_resize(images_chw, width, height)
    N, C = images_chw.shape[0], images_chw.shape[1]
    canvas = torch.zeros((N, C, height, width), device=images_chw.device, dtype=images_chw.dtype)
    y0 = (height - new_h) // 2
    x0 = (width - new_w) // 2
    canvas[:, :, y0:y0 + new_h, x0:x0 + new_w] = resized
    return canvas


def contain_blur_bg(
    images_chw: torch.Tensor,
    width: int,
    height: int,
    blur_sigma: float = 25.0,
    darken: float = 0.6,
) -> torch.Tensor:
    bg = cover(images_chw, width, height)
    k = _kernel_size_for_sigma(blur_sigma, min(height, width))
    bg = kornia.filters.gaussian_blur2d(bg, (k, k), (blur_sigma, blur_sigma))
    bg = bg * darken

    resized, new_w, new_h = _contain_resize(images_chw, width, height)
    canvas = bg.clone()
    y0 = (height - new_h) // 2
    x0 = (width - new_w) // 2
    canvas[:, :, y0:y0 + new_h, x0:x0 + new_w] = resized
    return canvas


def fit_batch(images_chw: torch.Tensor, width: int, height: int, fit_mode: str) -> torch.Tensor:
    if fit_mode == "cover":
        return cover(images_chw, width, height)
    if fit_mode == "contain_black_bg":
        return contain_black_bg(images_chw, width, height)
    if fit_mode == "contain_blur_bg":
        return contain_blur_bg(images_chw, width, height)
    raise ValueError(f"Unknown canvas fit mode: {fit_mode!r}. Available: {FIT_MODES}")
