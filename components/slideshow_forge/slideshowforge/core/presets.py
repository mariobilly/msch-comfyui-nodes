"""Style presets: weighted rule tables consumed by the timeline_builder rule engine.

Each preset is plain data (no code) so new presets/tuning can be added without
touching the rule engine. "weight" values are relative, not required to sum to 1.
"""

PRESETS = {
    "classic_ken_burns": {
        "display_name": "Classic Ken Burns",
        "segment_duration": {"min": 2.5, "max": 4.5},
        "transition_duration": {"min": 0.5, "max": 1.0},
        "motion_pool": [
            {"type": "zoom_in", "weight": 3, "param_ranges": {
                "scale_delta": [0.06, 0.20], "pan_x": [-0.03, 0.03], "pan_y": [-0.03, 0.03], "rot_deg": [0, 0]}},
            {"type": "zoom_out", "weight": 2, "param_ranges": {
                "scale_delta": [-0.20, -0.06], "pan_x": [-0.03, 0.03], "pan_y": [-0.03, 0.03], "rot_deg": [0, 0]}},
            {"type": "pan_left", "weight": 2, "param_ranges": {
                "scale_delta": [0.0, 0.04], "pan_x": [-0.10, -0.04], "pan_y": [-0.02, 0.02], "rot_deg": [0, 0]}},
            {"type": "pan_right", "weight": 2, "param_ranges": {
                "scale_delta": [0.0, 0.04], "pan_x": [0.04, 0.10], "pan_y": [-0.02, 0.02], "rot_deg": [0, 0]}},
        ],
        "transition_pool": [
            {"type": "crossfade", "weight": 6, "param_ranges": {}},
            {"type": "blur_dissolve", "weight": 1, "param_ranges": {"max_sigma": [3, 8]}},
        ],
        "easing_pool": [{"type": "ease_in_out", "weight": 1}],
        "guardrails": {
            "no_immediate_repeat_motion": True,
            "no_immediate_repeat_transition": True,
            "max_consecutive_same_type": 2,
        },
    },
    "dynamic_wipes": {
        "display_name": "Dynamic Wipes",
        "segment_duration": {"min": 1.5, "max": 3.0},
        "transition_duration": {"min": 0.3, "max": 0.6},
        "motion_pool": [
            {"type": "zoom_in", "weight": 2, "param_ranges": {
                "scale_delta": [0.05, 0.12], "pan_x": [-0.02, 0.02], "pan_y": [-0.02, 0.02], "rot_deg": [0, 0]}},
            {"type": "pan_left", "weight": 3, "param_ranges": {
                "scale_delta": [0.0, 0.05], "pan_x": [-0.14, -0.06], "pan_y": [-0.02, 0.02], "rot_deg": [0, 0]}},
            {"type": "pan_right", "weight": 3, "param_ranges": {
                "scale_delta": [0.0, 0.05], "pan_x": [0.06, 0.14], "pan_y": [-0.02, 0.02], "rot_deg": [0, 0]}},
            {"type": "ken_burns_diagonal", "weight": 2, "param_ranges": {
                "scale_delta": [0.05, 0.14], "pan_x": [-0.08, 0.08], "pan_y": [-0.08, 0.08], "rot_deg": [0, 0]}},
        ],
        "transition_pool": [
            {"type": "wipe_left", "weight": 2, "param_ranges": {"feather_px": [8, 24]}},
            {"type": "wipe_right", "weight": 2, "param_ranges": {"feather_px": [8, 24]}},
            {"type": "wipe_up", "weight": 1, "param_ranges": {"feather_px": [8, 24]}},
            {"type": "wipe_down", "weight": 1, "param_ranges": {"feather_px": [8, 24]}},
            {"type": "diagonal_wipe_tl", "weight": 2, "param_ranges": {"feather_px": [8, 24]}},
            {"type": "diagonal_wipe_br", "weight": 2, "param_ranges": {"feather_px": [8, 24]}},
            {"type": "crossfade", "weight": 1, "param_ranges": {}},
        ],
        "easing_pool": [
            {"type": "ease_in_out", "weight": 2},
            {"type": "ease_out", "weight": 1},
        ],
        "guardrails": {
            "no_immediate_repeat_motion": True,
            "no_immediate_repeat_transition": True,
            "max_consecutive_same_type": 2,
        },
    },
    "slow_cinematic": {
        "display_name": "Slow Cinematic",
        "segment_duration": {"min": 4.0, "max": 7.0},
        "transition_duration": {"min": 0.8, "max": 1.5},
        "motion_pool": [
            {"type": "zoom_in", "weight": 3, "param_ranges": {
                "scale_delta": [0.03, 0.09], "pan_x": [-0.015, 0.015], "pan_y": [-0.015, 0.015], "rot_deg": [0, 0]}},
            {"type": "zoom_out", "weight": 2, "param_ranges": {
                "scale_delta": [-0.09, -0.03], "pan_x": [-0.015, 0.015], "pan_y": [-0.015, 0.015], "rot_deg": [0, 0]}},
            {"type": "static", "weight": 1, "param_ranges": {
                "scale_delta": [0.0, 0.0], "pan_x": [0.0, 0.0], "pan_y": [0.0, 0.0], "rot_deg": [0, 0]}},
        ],
        "transition_pool": [
            {"type": "crossfade", "weight": 5, "param_ranges": {}},
            {"type": "blur_dissolve", "weight": 3, "param_ranges": {"max_sigma": [4, 10]}},
        ],
        "easing_pool": [{"type": "ease_in_out", "weight": 1}],
        "guardrails": {
            "no_immediate_repeat_motion": True,
            "no_immediate_repeat_transition": False,
            "max_consecutive_same_type": 3,
        },
    },
}


def list_preset_names() -> list:
    return list(PRESETS.keys())


def get_preset(name: str) -> dict:
    if name not in PRESETS:
        raise KeyError(f"Unknown SlideshowForge preset: {name!r}. Available: {list_preset_names()}")
    return PRESETS[name]
