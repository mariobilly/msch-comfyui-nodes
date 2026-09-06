"""Timeline JSON schema constants and validation for SlideshowForge."""

SCHEMA_VERSION = 1

MOTION_TYPES = (
    "static", "zoom_in", "zoom_out",
    "pan_left", "pan_right", "pan_up", "pan_down",
    "ken_burns_diagonal", "rotate_slow",
)

TRANSITION_TYPES = (
    "none", "crossfade",
    "wipe_left", "wipe_right", "wipe_up", "wipe_down",
    "diagonal_wipe_tl", "diagonal_wipe_br",
    "blur_dissolve",
)

EASING_TYPES = ("linear", "ease_in", "ease_out", "ease_in_out")

LAYOUT_TYPES = ("full_bleed",)

CANVAS_FIT_TYPES = ("cover", "contain_blur_bg", "contain_black_bg")

_MOTION_PARAM_KEYS = (
    "start_scale", "end_scale",
    "pan_x_start", "pan_x_end",
    "pan_y_start", "pan_y_end",
    "rotation_deg_start", "rotation_deg_end",
)


def validate_timeline(timeline: dict) -> list:
    """Validate a timeline dict against the SlideshowForge schema.

    Returns a list of human-readable error strings; empty list means valid.
    Does not raise -- callers decide how to react to failures.
    """
    errors = []

    if not isinstance(timeline, dict):
        return ["timeline must be a JSON object"]

    if timeline.get("version") != SCHEMA_VERSION:
        errors.append(f"version must be {SCHEMA_VERSION}, got {timeline.get('version')!r}")

    for key in ("seed", "fps", "total_duration"):
        if key not in timeline:
            errors.append(f"missing required top-level field: {key}")

    canvas = timeline.get("canvas")
    if not isinstance(canvas, dict):
        errors.append("canvas must be an object with width/height/fit")
    else:
        for key in ("width", "height"):
            if not isinstance(canvas.get(key), int) or canvas.get(key) <= 0:
                errors.append(f"canvas.{key} must be a positive integer")
        if canvas.get("fit") not in CANVAS_FIT_TYPES:
            errors.append(f"canvas.fit must be one of {CANVAS_FIT_TYPES}, got {canvas.get('fit')!r}")

    segments = timeline.get("segments")
    if not isinstance(segments, list) or len(segments) == 0:
        errors.append("segments must be a non-empty list")
        return errors

    for i, seg in enumerate(segments):
        prefix = f"segments[{i}]"
        if not isinstance(seg, dict):
            errors.append(f"{prefix} must be an object")
            continue

        if not isinstance(seg.get("image_index"), int) or seg.get("image_index") < 0:
            errors.append(f"{prefix}.image_index must be a non-negative integer")

        if not isinstance(seg.get("duration"), (int, float)) or seg.get("duration") <= 0:
            errors.append(f"{prefix}.duration must be a positive number")

        if seg.get("layout") not in LAYOUT_TYPES:
            errors.append(f"{prefix}.layout must be one of {LAYOUT_TYPES}, got {seg.get('layout')!r}")

        motion = seg.get("motion")
        if not isinstance(motion, dict):
            errors.append(f"{prefix}.motion must be an object")
        else:
            if motion.get("type") not in MOTION_TYPES:
                errors.append(f"{prefix}.motion.type must be one of {MOTION_TYPES}, got {motion.get('type')!r}")
            if motion.get("easing") not in EASING_TYPES:
                errors.append(f"{prefix}.motion.easing must be one of {EASING_TYPES}")
            params = motion.get("params")
            if not isinstance(params, dict):
                errors.append(f"{prefix}.motion.params must be an object")
            else:
                for key in _MOTION_PARAM_KEYS:
                    if key not in params or not isinstance(params[key], (int, float)):
                        errors.append(f"{prefix}.motion.params.{key} must be a number")

        transition = seg.get("transition_out")
        is_last = (i == len(segments) - 1)
        if transition is not None:
            if not isinstance(transition, dict):
                errors.append(f"{prefix}.transition_out must be an object or null")
            else:
                if transition.get("type") not in TRANSITION_TYPES:
                    errors.append(
                        f"{prefix}.transition_out.type must be one of {TRANSITION_TYPES}, "
                        f"got {transition.get('type')!r}"
                    )
                if transition.get("type") != "none":
                    if not isinstance(transition.get("duration"), (int, float)) or transition.get("duration") < 0:
                        errors.append(f"{prefix}.transition_out.duration must be a non-negative number")
                    if transition.get("easing") not in EASING_TYPES:
                        errors.append(f"{prefix}.transition_out.easing must be one of {EASING_TYPES}")
        elif not is_last:
            errors.append(f"{prefix}.transition_out must be present (may be type='none') on non-final segments")

    return errors
