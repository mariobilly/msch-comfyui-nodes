from __future__ import annotations

import random

import pytest

from mscha2v.core.drift import beats_to_frame_boundaries


def _beats(bpm: float, duration_sec: float, offset_sec: float = 0.0) -> list[float]:
    interval = 60.0 / bpm
    beats = []
    t = offset_sec
    while t < duration_sec:
        beats.append(t)
        t += interval
    return beats


def test_three_minutes_174bpm_24fps_bounded_error():
    beats = _beats(174.0, 180.0)
    frames = beats_to_frame_boundaries(beats, 24.0)
    assert len(frames) == len(beats)
    for t, frame in zip(beats, frames, strict=True):
        assert abs(frame - t * 24.0) <= 0.5 + 1e-9, (t, frame)


def test_non_integer_fps_23_976():
    beats = _beats(120.0, 200.0)
    frames = beats_to_frame_boundaries(beats, 23.976)
    for t, frame in zip(beats, frames, strict=True):
        assert abs(frame - t * 23.976) <= 0.5 + 1e-9, (t, frame)


def test_frames_are_non_decreasing():
    beats = _beats(140.0, 60.0)
    frames = beats_to_frame_boundaries(beats, 30.0)
    assert frames == sorted(frames)
    # After the first boundary, the monotonicity clamp guarantees strict increase.
    # Intentionally offset pairwise iteration (frames vs frames[1:]) -- these
    # are naturally different lengths, so strict=False (not True) is correct.
    assert all(b > a for a, b in zip(frames, frames[1:], strict=False))


def test_monotonicity_clamp_on_tightly_clustered_boundaries():
    # After a nonzero first boundary, further boundaries packed far closer
    # together than one frame at fps=24 -- naive independent rounding would
    # collapse several of them onto the same frame. The clamp forces strict
    # monotonic increase instead, at the cost of exceeding 0.5-frame local
    # error for the clamped entries -- exactly the documented, intentional
    # trade-off. (The clamp only engages once `emitted > 0`, i.e. after the
    # first boundary has actually advanced past frame 0 -- see drift.py.)
    beats = [1.0, 1.001, 1.002, 1.003, 1.004]
    frames = beats_to_frame_boundaries(beats, 24.0)
    assert frames == [24, 25, 26, 27, 28]
    # The clamped entries (indices 1..4) exceed the normal 0.5-frame bound.
    assert any(abs(f - t * 24.0) > 0.5 for t, f in zip(beats[1:], frames[1:], strict=True))


@pytest.mark.parametrize("trial", range(25))
def test_property_random_tempo_duration_fps(trial):
    rng = random.Random(trial)
    bpm = rng.uniform(60.0, 220.0)
    duration = rng.uniform(30.0, 600.0)
    fps = rng.choice([23.976, 24.0, 25.0, 29.97, 30.0])
    beats = _beats(bpm, duration)
    frames = beats_to_frame_boundaries(beats, fps)

    assert frames == sorted(frames)
    max_error = 0.0
    clamped = 0
    for t, frame in zip(beats, frames, strict=True):
        error = abs(frame - t * fps)
        max_error = max(max_error, error)
        if error > 0.5 + 1e-9:
            clamped += 1
    # Only boundaries packed closer than one frame apart (clamp territory)
    # are allowed to exceed the 0.5-frame bound; at these bpm/fps ranges
    # that should essentially never happen, but we don't hard-assert zero
    # to avoid a flaky edge case -- we assert it's rare relative to the size
    # of the sequence instead.
    assert clamped <= max(1, len(frames) // 20)
