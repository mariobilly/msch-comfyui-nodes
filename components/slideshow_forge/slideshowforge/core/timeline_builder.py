"""Rule engine: images + preset + seed + duration -> timeline dict.

RNG CONSUMPTION ORDER -- DO NOT REORDER. If this order must ever change,
bump schema.SCHEMA_VERSION, since it changes what a given seed produces.

  1. shuffle_order (if enabled): rng.shuffle(image_order)
  2. transition durations, one per gap, in gap order
  3. (total_duration mode only) raw per-segment durations, in segment order
  4. [no rng] duration solve / clamp / water-fill / repair
  5. per segment, in order: motion type -> motion params (scale_delta, pan_x,
     pan_y, rot_deg, in that order) -> motion easing
  6. per transition gap (skipped on the final segment unless loop=True), in
     order: transition type -> transition params (sorted param_ranges keys)
     -> transition easing

beat_sync mode reuses this exact order -- only step 3 changes (segment
durations come from the detected beat grid instead of a random sample), and
transition durations are still drawn from the preset's transition_duration
range in step 2, same as per_image_duration mode.
"""

import random

from . import schema
from .presets import get_preset
from .rng import pick_with_guardrails, sample_range, weighted_choice

_MOTION_PARAM_SAMPLE_ORDER = ("scale_delta", "pan_x", "pan_y", "rot_deg")

_WATER_FILL_MAX_ITERATIONS = 3
_TRANSITION_VS_SEGMENT_MIN_RATIO = 2.0
_TRANSITION_REPAIR_FACTOR = 0.4


def _solve_total_duration_segments(rng, n_segments, n_transitions, preset, total_duration):
    t_range = preset["transition_duration"]
    transition_durations = [
        sample_range(rng, t_range["min"], t_range["max"]) for _ in range(n_transitions)
    ]

    s_range = preset["segment_duration"]
    raw = [sample_range(rng, s_range["min"], s_range["max"]) for _ in range(n_segments)]

    target_sum = total_duration + sum(transition_durations)
    sum_raw = sum(raw)
    k = (target_sum / sum_raw) if sum_raw > 0 else 1.0
    durations = [r * k for r in raw]

    clamped = [False] * n_segments
    # Clamp before the water-fill loop: if the initial scale factor alone
    # already pushes every duration past a bound (e.g. total_duration is
    # infeasible for this many segments at this preset's per-segment
    # minimum), sum(durations) already equals target_sum, so the loop's
    # diff-based exit below would fire on iteration 1 and skip clamping
    # entirely, silently violating the preset's own min/max.
    for i in range(n_segments):
        if durations[i] < s_range["min"]:
            durations[i] = s_range["min"]
            clamped[i] = True
        elif durations[i] > s_range["max"]:
            durations[i] = s_range["max"]
            clamped[i] = True

    for _ in range(_WATER_FILL_MAX_ITERATIONS):
        current_sum = sum(durations)
        diff = target_sum - current_sum
        if abs(diff) < 1e-9:
            break
        unclamped = [i for i in range(n_segments) if not clamped[i]]
        if not unclamped:
            break
        weight_sum = sum(durations[i] for i in unclamped)
        for i in unclamped:
            share = (durations[i] / weight_sum) if weight_sum > 0 else (1.0 / len(unclamped))
            durations[i] += diff * share
        for i in unclamped:
            if durations[i] < s_range["min"]:
                durations[i] = s_range["min"]
                clamped[i] = True
            elif durations[i] > s_range["max"]:
                durations[i] = s_range["max"]
                clamped[i] = True

    residual = target_sum - sum(durations)
    return durations, transition_durations, residual


def _solve_beat_sync_segments(beats_sec, audio_duration_sec, image_count, beats_per_image):
    """Segment durations spanning the FULL audio duration (0 .. audio_duration_sec),
    using detected beat timestamps only to place the internal cut points between
    segments. This deliberately does not truncate to the detected-beat span --
    a beatless intro/outro (ambient build-up, fade, etc.) is absorbed into the
    first/last segment's dwell time rather than being silently dropped, which
    would otherwise produce a much shorter video than the loaded audio.

    Returns (durations, n_segments) -- n_segments may be less than image_count
    if there aren't enough detected beats to place a cut for every image; the
    caller truncates image_order to match and should warn the user.
    """
    max_internal_cuts = len(beats_sec) // beats_per_image
    n_segments = max(1, min(image_count, max_internal_cuts + 1))

    boundaries = [0.0]
    for i in range(1, n_segments):
        boundaries.append(beats_sec[i * beats_per_image - 1])
    boundaries.append(max(audio_duration_sec, boundaries[-1] + 0.1))

    durations = [max(boundaries[i + 1] - boundaries[i], 0.1) for i in range(n_segments)]
    return durations, n_segments


def _apply_transition_repair(durations, transition_durations):
    for i, t_dur in enumerate(transition_durations):
        owning_segment_duration = durations[i]
        if owning_segment_duration < _TRANSITION_VS_SEGMENT_MIN_RATIO * t_dur:
            transition_durations[i] = owning_segment_duration * _TRANSITION_REPAIR_FACTOR


def _sample_motion(rng, preset, history):
    choice = pick_with_guardrails(
        rng, preset["motion_pool"], history, preset["guardrails"], "motion_type"
    )
    ranges = choice["param_ranges"]
    sampled = {}
    for key in _MOTION_PARAM_SAMPLE_ORDER:
        lo, hi = ranges.get(key, [0, 0])
        sampled[key] = sample_range(rng, lo, hi)

    easing = weighted_choice(rng, preset["easing_pool"])["type"]

    # Scale must never go below 1.0: the canvas-fitted source image has no
    # content beyond its own edges, so scale_t < 1.0 would sample outside
    # its bounds (reflection-padding artifacts at the frame edges). Instead
    # of always starting at 1.0, put whichever end is >= 1.0 at the end
    # implied by the sign of scale_delta -- "zoom in" ramps 1.0 -> higher,
    # "zoom out" ramps higher -> 1.0 -- so both endpoints stay >= 1.0.
    scale_delta = sampled["scale_delta"]
    if scale_delta >= 0:
        start_scale, end_scale = 1.0, 1.0 + scale_delta
    else:
        start_scale, end_scale = 1.0 - scale_delta, 1.0

    params = {
        "start_scale": start_scale,
        "end_scale": end_scale,
        "pan_x_start": 0.0,
        "pan_x_end": sampled["pan_x"],
        "pan_y_start": 0.0,
        "pan_y_end": sampled["pan_y"],
        "rotation_deg_start": 0.0,
        "rotation_deg_end": sampled["rot_deg"],
    }
    return {"type": choice["type"], "easing": easing, "params": params}


def _sample_transition(rng, preset, history, duration):
    choice = pick_with_guardrails(
        rng, preset["transition_pool"], history, preset["guardrails"], "transition_type"
    )
    ranges = choice["param_ranges"]
    params = {}
    for key in sorted(ranges.keys()):
        lo, hi = ranges[key]
        params[key] = sample_range(rng, lo, hi)

    easing = weighted_choice(rng, preset["easing_pool"])["type"]

    return {"type": choice["type"], "duration": duration, "easing": easing, "params": params}


def build_timeline(
    image_count: int,
    preset_name: str,
    duration_mode: str,
    total_duration: float,
    per_image_duration: float,
    fps: int,
    seed: int,
    shuffle_order: bool = False,
    loop: bool = False,
    canvas_fit: str = "cover",
    canvas_width: int = 1920,
    canvas_height: int = 1080,
    beats_sec: list = None,
    beats_per_image: int = 2,
    bpm: float = None,
    audio_duration_sec: float = None,
) -> dict:
    if image_count < 1:
        raise ValueError("image_count must be >= 1")

    preset = get_preset(preset_name)
    rng = random.Random(seed)

    image_order = list(range(image_count))
    if shuffle_order:
        rng.shuffle(image_order)

    if duration_mode == "beat_sync":
        if not beats_sec or audio_duration_sec is None:
            raise ValueError(
                "SlideshowForge: duration_mode='beat_sync' requires analyzed audio "
                "(beats_sec/audio_duration_sec) -- this should be supplied by the Director "
                "node, not passed empty directly."
            )
        durations, n_segments = _solve_beat_sync_segments(
            beats_sec, audio_duration_sec, image_count, beats_per_image
        )
        image_order = image_order[:n_segments]
        # Loop-back timing has no natural meaning against a fixed beat grid
        # (there's no beat "after" the last one used) -- ignored in this mode.
        n_transitions = max(0, n_segments - 1)
        t_range = preset["transition_duration"]
        transition_durations = [
            sample_range(rng, t_range["min"], t_range["max"]) for _ in range(n_transitions)
        ]
        residual = 0.0
    else:
        n_segments = image_count
        n_transitions = n_segments if (loop and n_segments > 1) else max(0, n_segments - 1)

        if duration_mode == "total_duration":
            durations, transition_durations, residual = _solve_total_duration_segments(
                rng, n_segments, n_transitions, preset, total_duration
            )
        elif duration_mode == "per_image_duration":
            durations = [per_image_duration] * n_segments
            t_range = preset["transition_duration"]
            transition_durations = [
                sample_range(rng, t_range["min"], t_range["max"]) for _ in range(n_transitions)
            ]
            residual = 0.0
        else:
            raise ValueError(f"Unknown duration_mode: {duration_mode!r}")

    _apply_transition_repair(durations, transition_durations)

    motion_history = []
    transition_history = []
    segments = []

    for i in range(n_segments):
        motion = _sample_motion(rng, preset, motion_history)
        motion_history.append({"motion_type": motion["type"]})

        transition_out = None
        if i < n_transitions:
            transition_out = _sample_transition(rng, preset, transition_history, transition_durations[i])
            transition_history.append({"transition_type": transition_out["type"]})

        segments.append({
            "index": i,
            "image_index": image_order[i],
            "duration": durations[i],
            "layout": "full_bleed",
            "motion": motion,
            "transition_out": transition_out,
        })

    effective_total_duration = sum(durations) - sum(transition_durations)

    timeline = {
        "version": schema.SCHEMA_VERSION,
        "seed": seed,
        "preset": preset_name,
        "fps": fps,
        "canvas": {"width": canvas_width, "height": canvas_height, "fit": canvas_fit},
        "total_duration": effective_total_duration,
        "duration_solve_residual": residual,
        "loop": loop,
        "duration_mode": duration_mode,
        "audio_sync": (
            {"bpm": bpm, "beats_per_image": beats_per_image} if duration_mode == "beat_sync" else None
        ),
        "segments": segments,
    }

    errors = schema.validate_timeline(timeline)
    if errors:
        raise RuntimeError(
            "SlideshowForge internal error: generated timeline failed schema validation: " + "; ".join(errors)
        )

    return timeline
