from __future__ import annotations

import random

import pytest

from mscha2v.core.buckets import (
    MAX_TRAINED_FRAMES,
    MIN_TRAINED_FRAMES,
    OFFSET,
    STEP,
    BucketOverflowError,
    align_frame_count,
    solve_bucket,
)


def test_grid_constants_match_introspected_h3_pack():
    # comfyui-minimax-h3-audio-T8 core.py:14-28 -- the "17n+5" grid.
    assert STEP == 17
    assert OFFSET == 5
    assert MIN_TRAINED_FRAMES == 124
    assert MAX_TRAINED_FRAMES == 362


def test_exact_hit_at_min_trained_frames():
    assert solve_bucket(124) == (124, 0)


def test_mid_grid_pad_case():
    # Next grid point after 124 is 141 (124 + 17); 130 pads up to it.
    assert solve_bucket(130) == (141, 11)


def test_second_exact_hit():
    assert solve_bucket(141) == (141, 0)


def test_exact_hit_at_max_trained_frames():
    assert solve_bucket(362) == (362, 0)


def test_short_request_clamped_to_min_trained_frames():
    # 10 frames aligns to 22 on the raw grid, but H3 is not trained below
    # MIN_TRAINED_FRAMES, so solve_bucket must clamp up further.
    bucket_frames, trim_tail = solve_bucket(10)
    assert bucket_frames == MIN_TRAINED_FRAMES
    assert trim_tail == MIN_TRAINED_FRAMES - 10


def test_overflow_above_max_trained_frames_raises_with_guidance():
    with pytest.raises(BucketOverflowError, match="(?i)split"):
        solve_bucket(363)


def test_zero_or_negative_frames_rejected():
    with pytest.raises(ValueError):
        solve_bucket(0)


@pytest.mark.parametrize("trial", range(50))
def test_property_random_n(trial):
    rng = random.Random(trial)
    n = rng.randint(1, 500)
    expected_aligned = align_frame_count(n)
    expected_bucket = max(expected_aligned, MIN_TRAINED_FRAMES)

    if expected_bucket > MAX_TRAINED_FRAMES:
        with pytest.raises(BucketOverflowError):
            solve_bucket(n)
        return

    bucket_frames, trim_tail = solve_bucket(n)
    assert bucket_frames == expected_bucket
    assert bucket_frames >= n
    assert MIN_TRAINED_FRAMES <= bucket_frames <= MAX_TRAINED_FRAMES
    assert (bucket_frames - OFFSET) % STEP == 0
    assert trim_tail == bucket_frames - n
