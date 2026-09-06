"""Sub-frame drift correction: beat times (continuous) -> frame indices (1/fps quanta).

Naive per-segment rounding (round each segment's length independently and
accumulate) drifts arbitrarily far from the audio over a long timeline,
because rounding error compounds every boundary. The fix used here never
accumulates rounding error: every boundary's frame index is derived from its
*absolute* time (`round(t * fps)`), not from the previous boundary's already-
rounded frame plus a rounded delta. That guarantees the cumulative timeline
never drifts more than 0.5 frames from the audio at any single boundary, no
matter how long the track runs.

The one exception is monotonicity: if two boundaries are closer together than
half a frame, quantizing both independently could produce a non-increasing
(or decreasing) frame sequence, which is meaningless for a video timeline.
When that happens we clamp the later boundary to `previous_frame + 1` -- this
is the one place a boundary's local error can exceed 0.5 frames, and it is
intentional and tested explicitly (see test_drift.py).
"""

from __future__ import annotations


def beats_to_frame_boundaries(boundary_times_sec: list[float], fps: float) -> list[int]:
    """Monotonic boundary times (seconds) -> integer frame indices.

    At every boundary, `abs(assigned_frame - t*fps) <= 0.5`, except where the
    monotonicity clamp (see module docstring) had to force a later boundary
    at least one frame past its predecessor.
    """
    if fps <= 0:
        raise ValueError("fps must be > 0")

    frames: list[int] = []
    emitted = 0
    for t in boundary_times_sec:
        exact = t * fps
        n = round(exact) - emitted
        n = max(n, 1) if emitted > 0 else max(n, 0)
        emitted += n
        frames.append(emitted)
    return frames
