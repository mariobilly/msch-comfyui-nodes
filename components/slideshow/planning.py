"""Serializable shot plans shared by the director and the renderer."""

import copy
import math

import numpy as np


PRESETS = {
    "High energy": (("hero", "split", "stack", "triptych", "mosaic"),
                    ("cut", "whip", "zoom", "diagonal", "shutter", "impact"),
                    ("snap", "push", "pull", "left", "right", "rise"), 1.0),
    "Luxury editorial": (("hero", "gallery", "split"),
                         ("cut", "dissolve", "diagonal"),
                         ("push", "pull", "left", "right"), 0.35),
    "Cinematic gallery": (("hero", "window", "gallery"), ("dissolve", "cut"),
                          ("push", "pull", "rise", "left", "right"), 0.22),
    "Hard-cut promo": (("hero", "split", "triptych", "mosaic"), ("cut",),
                       ("hold", "snap", "left", "right", "pull"), 0.8),
}
SCENE_NAMES = {"hero", "split", "stack", "triptych", "gallery", "window", "mosaic"}
TRANSITION_NAMES = {"whip", "zoom", "diagonal", "shutter", "impact", "cut", "dissolve"}
MOTION_NAMES = {"push", "pull", "left", "right", "rise", "snap", "hold"}


def _choose(rng, choices, history):
    available = [item for item in choices if not history or item != history[-1]] or list(choices)
    weights = np.array([0.35 if item in history[-3:] else 1.0 for item in available])
    return str(rng.choice(available, p=weights / weights.sum()))


def _pace_factors(count, preset, pacing, rng):
    if pacing == "Even" or count == 1:
        return [1.0] * count
    factors = []
    for index in range(count):
        # This is an editorial arc, not inferred musical section detection.
        position = index / max(1, count - 1)
        if index == 0 or index == count - 1:
            factor = 1.5
        elif preset in ("Luxury editorial", "Cinematic gallery"):
            factor = float(rng.choice([1.0, 1.5, 2.0]))
        elif 0.4 < position < 0.6:
            factor = float(rng.choice([1.0, 1.5]))
        else:
            factor = float(rng.choice([0.5, 0.5, 1.0]))
        if len(factors) >= 2 and factors[-2:] == [factor, factor]:
            factor = 1.0 if factor != 1.0 else 0.5
        factors.append(factor)
    return factors


def beat_boundaries(image_count, beats, beats_per_image, pacing, factors=None):
    if beats.get("version") != 1:
        raise ValueError("Unsupported beat data. Run Beat Analyzer again.")
    if not float(beats_per_image).is_integer():
        raise ValueError("Detected-beat timing needs a whole number of beats per image.")
    times = np.asarray(beats.get("times", []), dtype=float)
    if times.ndim != 1 or len(times) < 2 or not np.isfinite(times).all() or (np.diff(times) <= 0).any():
        raise ValueError("Beat markers must be finite, strictly increasing times.")
    times = times[times > 0.001]
    boundaries = [0.0]
    cursor = -1
    for index in range(image_count):
        half = pacing == "Dynamic" and image_count > 1 and index % 8 in (1, 3, 5, 6)
        factor = factors[index] if factors is not None else (0.5 if half else 1.0)
        step = max(1, round(beats_per_image * factor))
        cursor += step
        while cursor < len(times) and times[cursor] - boundaries[-1] < 0.4 - 1e-8:
            cursor += 1
        if cursor >= len(times):
            raise ValueError("Not enough detected beats for every image. Reduce beats_per_image/image count, or use a longer soundtrack.")
        boundaries.append(float(times[cursor]))
    return boundaries


def build_plan(image_count, preset="High energy", timing="BPM", bpm=128,
               beats_per_image=4, seconds_per_image=2, pacing="Dynamic", headlines="",
               shuffle=False, seed=0, beats=None):
    if not isinstance(image_count, int) or not 1 <= image_count <= 200:
        raise ValueError("image_count must be between 1 and 200.")
    if preset not in PRESETS or timing not in ("BPM", "Seconds") or pacing not in ("Dynamic", "Even"):
        raise ValueError("Unknown director preset, timing or pacing.")
    if not 20 <= bpm <= 300 or not 1 <= beats_per_image <= 16 or not 0.4 <= seconds_per_image <= 30:
        raise ValueError("Invalid director timing values.")
    labels = headlines.splitlines()
    if len(labels) > image_count:
        raise ValueError("There are more headline lines than source images.")
    labels += [""] * (image_count - len(labels))
    order = list(range(image_count))
    if shuffle:
        np.random.default_rng(seed).shuffle(order)
    rng = np.random.default_rng(seed)
    factors = _pace_factors(image_count, preset, pacing, rng)
    if beats is not None:
        boundaries = beat_boundaries(image_count, beats, beats_per_image, pacing, factors)
    else:
        base = 60 / bpm * beats_per_image if timing == "BPM" else seconds_per_image
        boundaries = [0.0]
        for index in range(image_count):
            boundaries.append(boundaries[-1] + max(0.4, base * factors[index]))
    scenes, transitions, motions, strength = PRESETS[preset]
    shots = []
    for i, source in enumerate(order):
        scene = _choose(rng, scenes, [shot["scene"] for shot in shots])
        if i in (0, image_count - 1):
            scene = "hero"
        motion = _choose(rng, motions, [shot["motion"] for shot in shots])
        transition = _choose(rng, transitions, [shot["transition"] for shot in shots])
        shots.append({"image_index": source, "duration": round(boundaries[i + 1] - boundaries[i], 6),
                      "scene": scene, "transition": transition, "headline": labels[source],
                      "motion": motion, "strength": strength, "variant": int(rng.integers(0, 8))})
    return {"version": 1, "source_count": image_count, "preset": preset,
            "timing_source": "detected beats" if beats is not None else timing, "shots": shots}


def validate_plan(plan, source_count):
    if not isinstance(plan, dict) or plan.get("version") != 1:
        raise ValueError("The timeline must be a version 1 marioslideshow plan.")
    if plan.get("source_count") != source_count:
        raise ValueError("The plan's source_count does not match the connected images.")
    shots = plan.get("shots")
    if not isinstance(shots, list) or not 1 <= len(shots) <= 200:
        raise ValueError("The timeline must contain 1-200 shots.")
    required = {"image_index", "duration", "scene", "transition", "headline"}
    for index, shot in enumerate(shots):
        optional = {"motion", "strength", "variant"}
        if not isinstance(shot, dict) or not required <= set(shot) or set(shot) - required - optional:
            raise ValueError(f"Shot {index + 1} needs {', '.join(sorted(required))}; optional: motion, strength, variant.")
        if type(shot["image_index"]) is not int or not 0 <= shot["image_index"] < source_count:
            raise ValueError(f"Shot {index + 1}: image_index is outside the source collection (zero-based).")
        duration = shot["duration"]
        if type(duration) not in (int, float) or not math.isfinite(duration) or not 0.4 <= duration <= 120:
            raise ValueError(f"Shot {index + 1}: duration must be 0.4-120 seconds.")
        if shot["scene"] not in SCENE_NAMES or shot["transition"] not in TRANSITION_NAMES:
            raise ValueError(f"Shot {index + 1}: unknown scene or transition.")
        if not isinstance(shot["headline"], str) or len(shot["headline"]) > 240:
            raise ValueError(f"Shot {index + 1}: headline must be at most 240 characters.")
        if "motion" in shot and shot["motion"] not in MOTION_NAMES:
            raise ValueError(f"Shot {index + 1}: unknown motion.")
        strength = shot.get("strength", 1.0)
        if type(strength) not in (int, float) or not math.isfinite(strength) or not 0 <= strength <= 1:
            raise ValueError(f"Shot {index + 1}: strength must be between 0 and 1.")
        variant = shot.get("variant", 0)
        if type(variant) is not int or not 0 <= variant <= 7:
            raise ValueError(f"Shot {index + 1}: variant must be an integer from 0 to 7.")
    return copy.deepcopy(plan)


def validate_focus(focus, source_count):
    if not isinstance(focus, dict) or focus.get("version") != 1 or len(focus.get("items", [])) != source_count:
        raise ValueError("Framing data must match the number of connected source images.")
    for item in focus["items"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid framing item.")
        for field in ("x", "y"):
            value = item.get(field)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Focus x and y must be normalized numbers between 0 and 1.")
        box = item.get("box")
        if box is not None:
            if not isinstance(box, (list, tuple)) or len(box) != 4 or not all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in box):
                raise ValueError("Focus box must be [left, top, right, bottom] between 0 and 1.")
            if box[0] >= box[2] or box[1] >= box[3]:
                raise ValueError("Focus box must have positive width and height.")
    return copy.deepcopy(focus)
