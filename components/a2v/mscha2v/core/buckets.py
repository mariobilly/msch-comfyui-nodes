"""MiniMax H3 render-length bucket solver.

MiniMax H3 only accepts frame counts on a rigid grid: `frame_count =
offset + k*step` (the installed H3 pack, comfyui-minimax-h3-audio-T8, uses
step=17, offset=5 -- i.e. a "17n+5" grid; see `core.py:14-28`,
`align_frame_count`). Valid render windows additionally have a trained
minimum and maximum length (MIN_TRAINED_FRAMES=124 / ~5.17s,
MAX_TRAINED_FRAMES=362 / ~15.1s at FPS=24). Requesting an off-grid or
out-of-range length crashes the sampler with a tensor shape mismatch.

This module is a documented, pure-Python *mirror* of that pack's
`align_frame_count` -- it has zero ComfyUI/torch imports so it stays
importable and testable with plain pytest, no ComfyUI install and no GPU
required. Parameters are loaded from `mscha2v/h3/buckets.json`, which is
user-editable: if a future H3 checkpoint changes the grid, update that file.
`mscha2v/h3/adapter.py` calls the *real*, live H3 pack function at render
time as the runtime authority; this module is the offline/UI-side/tested
planning copy.
"""

from __future__ import annotations

import json
from pathlib import Path

_BUCKETS_JSON_PATH = Path(__file__).resolve().parent.parent / "h3" / "buckets.json"

_FALLBACK_PARAMS = {
    "step": 17,
    "offset": 5,
    "min_frames": 124,
    "max_frames": 362,
    "fps": 24,
    "audio_latent_fps": 40,
}


def _load_params() -> dict:
    try:
        with open(_BUCKETS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return dict(_FALLBACK_PARAMS)
    params = dict(_FALLBACK_PARAMS)
    for key in _FALLBACK_PARAMS:
        if key in data:
            params[key] = data[key]
    return params


_PARAMS = _load_params()
STEP: int = int(_PARAMS["step"])
OFFSET: int = int(_PARAMS["offset"])
MIN_TRAINED_FRAMES: int = int(_PARAMS["min_frames"])
MAX_TRAINED_FRAMES: int = int(_PARAMS["max_frames"])
FPS: int = int(_PARAMS["fps"])
AUDIO_LATENT_FPS: int = int(_PARAMS["audio_latent_fps"])


class BucketOverflowError(ValueError):
    """Raised when a shot's frame span exceeds MAX_TRAINED_FRAMES even after grid alignment."""


def align_frame_count(n: int) -> int:
    """Snap n up to the nearest `offset + k*step` grid point >= n.

    Mirrors comfyui-minimax-h3-audio-T8/core.py:25-28 exactly.
    """
    n = max(OFFSET, int(n))
    return n + ((OFFSET - n) % STEP)


def solve_bucket(n_frames: int) -> tuple[int, int]:
    """Return (bucket_frames, trim_tail) for the smallest valid H3 render window >= n_frames.

    `bucket_frames` is grid-aligned and clamped up to MIN_TRAINED_FRAMES (H3
    is not trained on shorter windows even if a shorter length happens to sit
    on the grid). `trim_tail = bucket_frames - n_frames` is the number of
    padding frames to slice back off after render.

    Raises BucketOverflowError if the aligned length exceeds
    MAX_TRAINED_FRAMES (~15.1s at 24fps) -- the caller should split the
    block/shot into smaller pieces.
    """
    if n_frames <= 0:
        raise ValueError("n_frames must be > 0")
    bucket_frames = align_frame_count(n_frames)
    if bucket_frames < MIN_TRAINED_FRAMES:
        bucket_frames = MIN_TRAINED_FRAMES
    if bucket_frames > MAX_TRAINED_FRAMES:
        raise BucketOverflowError(
            f"Requested {n_frames} frames aligns to {bucket_frames} frames, which exceeds "
            f"MiniMax H3's MAX_TRAINED_FRAMES={MAX_TRAINED_FRAMES} (~{MAX_TRAINED_FRAMES / FPS:.1f}s "
            f"at {FPS}fps). Split this block (or group) into two or more shots so each one's "
            f"span is <= {MAX_TRAINED_FRAMES} frames."
        )
    return bucket_frames, bucket_frames - n_frames
