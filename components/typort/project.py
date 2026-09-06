"""Validated, portable typography timelines. All geometry is normalized to the canvas."""
import copy
import json
import math
import re

FONTS = ["Black", "ExtraBold", "Bold", "Medium", "Regular", "Light", "ExtraLight"]
PRESETS = ["Line reveal", "Word cascade", "Scale impact", "Editorial drift", "Side sweep",
           "Tracking reveal", "Rise", "Fade", "Static"]
FORMATS = ["Transparent MOV", "PNG sequence", "MP4 composite"]
EASINGS = ["Smooth", "Power out", "Linear", "Custom"]
SOURCES = ["Mix", "Low band", "Mid band", "High band", "Drums", "Bass", "Vocals", "Other"]


def audio_track():
    return dict(file="", trim_start=0, trim_end=0, start=0, gain=1, muted=False,
                bpm_override=0, beat_offset=0, analysis=None)


def layer(text="MAKE\nIT MATTER", font="Black", preset="Line reveal", duration=5):
    return dict(text=text, font=font, preset=preset, start=0, end=duration, x=0.5, y=0.5,
                width=0.9, height=0.8, size=0.40, fit=True, align="center", direction="auto",
                line_height=1.0, tracking=0, color="#FFFFFF", opacity=1,
                stroke_color="#111111", stroke=0, shadow_color="#000000", shadow_opacity=0.45,
                shadow_blur=0.015, shadow_x=0.005, shadow_y=0.012,
                block_color="#DEFF4A", block_opacity=0, padding=0.015,
                rotation=0, scale=1, anchor_x=0.5, anchor_y=0.5,
                enter=0.8, exit=0.5, stagger=0.12, distance=0.10,
                easing="Power out", curve=[0.22, 1, 0.36, 1], enabled=True, keyframes=[],
                react_mode="Off", react_source="Mix", sensitivity=1, threshold=0.1,
                attack=0, decay=0.18, beat_every=1, beat_phase=0,
                react_outline=0.006, react_scale=0.04, react_x=0, react_y=0,
                react_opacity=0, react_shadow=0)


def default_project(text="MAKE\nIT MATTER", font="Black", preset="Line reveal", duration=5):
    return dict(version=1, duration=duration, background="#121416", video_offset=0,
                markers=[], text_cues=[], cues_visible=True, audio=audio_track(), layers=[layer(text, font, preset, duration)])


def number(value, name, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be a finite number between {low} and {high}.")


def color(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"{name} must be a #RRGGBB color.")


def validate_project(value):
    if isinstance(value, str):
        if len(value) > 8_000_000:
            raise ValueError("Project JSON is too large.")
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid typography project JSON: {exc.msg}.") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("Expected a version 1 mariotyport project.")
    p = copy.deepcopy(value)
    number(p.get("duration"), "duration", 0.1, 600)
    color(p.get("background"), "background")
    number(p.get("video_offset", 0), "video_offset", 0, 36000)
    p.setdefault("video_offset", 0)
    track = p.setdefault("audio", audio_track())
    if not isinstance(track, dict) or set(track) - set(audio_track()):
        raise ValueError("Invalid audio track fields.")
    p["audio"] = track = {**audio_track(), **track}
    if not isinstance(track["file"], str) or len(track["file"]) > 2000 or type(track["muted"]) is not bool:
        raise ValueError("Invalid audio file or mute value.")
    for name, limits in {"trim_start": (0, 600), "trim_end": (0, 600), "start": (0, 600),
                         "gain": (0, 2), "bpm_override": (0, 300), "beat_offset": (-5, 5)}.items():
        number(track[name], "audio " + name, *limits)
    if track["bpm_override"] and track["bpm_override"] < 20:
        raise ValueError("Manual BPM must be 20-300, or 0 for detected tempo.")
    if track["file"] and track["trim_end"] <= track["trim_start"]:
        raise ValueError("Audio out must be after audio in.")
    analysis = track["analysis"]
    if analysis is not None:
        validate_analysis(analysis)
        if analysis["file"] != track["file"]:
            raise ValueError("Audio changed. Analyze the new soundtrack before rendering.")
        if track["trim_end"] > analysis["duration"] + 0.05:
            raise ValueError("Audio out is beyond the analyzed range.")
    markers = p.setdefault("markers", [])
    if not isinstance(markers, list) or len(markers) > 5000:
        raise ValueError("Use at most 5000 timeline markers.")
    for marker in markers:
        number(marker, "marker", 0, p["duration"])
    cues = p.setdefault("text_cues", [])
    if not isinstance(cues, list) or len(cues) > 500 or type(p.setdefault("cues_visible", True)) is not bool:
        raise ValueError("Use at most 500 text cues and a boolean cue visibility.")
    previous_end = 0
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) != {"start", "end"}:
            raise ValueError("Text cues need start and end times.")
        number(cue["start"], "cue start", previous_end, p["duration"])
        number(cue["end"], "cue end", cue["start"], p["duration"])
        if cue["end"] <= cue["start"]:
            raise ValueError("Cue end must be after start.")
        previous_end = cue["end"]
    layers = p.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 60:
        raise ValueError("Use 1-60 typography layers.")
    for i, original in enumerate(layers):
        if not isinstance(original, dict) or set(original) - set(layer()):
            raise ValueError(f"Layer {i + 1} contains unknown fields.")
        item = {**layer(duration=p["duration"]), **original}
        layers[i] = item
        if not isinstance(item["text"], str) or not 1 <= len(item["text"]) <= 2000:
            raise ValueError(f"Layer {i + 1}: text must contain 1-2000 characters.")
        if item["font"] not in FONTS or item["preset"] not in PRESETS or item["easing"] not in EASINGS:
            raise ValueError(f"Layer {i + 1}: unknown font, animation or easing.")
        if item["react_mode"] not in ("Off", "Beats", "Hits", "Energy") or item["react_source"] not in SOURCES:
            raise ValueError("Unknown audio reaction mode or source.")
        if item["react_mode"] != "Off":
            if analysis is None or item["react_source"] not in analysis["channels"]:
                raise ValueError("Analyze the soundtrack/source before enabling audio reactions.")
        if item["align"] not in ("left", "center", "right") or item["direction"] not in ("auto", "ltr", "rtl"):
            raise ValueError("Unknown text alignment or direction.")
        for name in ("enabled", "fit"):
            if type(item[name]) is not bool:
                raise ValueError(f"{name} must be true or false.")
        ranges = {"start": (0, p["duration"]), "end": (0, p["duration"]),
                  "x": (-1, 2), "y": (-1, 2), "width": (0.02, 2), "height": (0.02, 2),
                  "size": (0.005, 1.5), "line_height": (0.5, 3), "tracking": (-0.02, 0.1),
                  "opacity": (0, 1), "stroke": (0, 0.05), "shadow_opacity": (0, 1),
                  "shadow_blur": (0, 0.1), "shadow_x": (-0.5, 0.5), "shadow_y": (-0.5, 0.5),
                  "block_opacity": (0, 1), "padding": (0, 0.15), "rotation": (-360, 360),
                  "scale": (0.05, 5), "anchor_x": (0, 1), "anchor_y": (0, 1),
                  "enter": (0, 30), "exit": (0, 30), "stagger": (0, 2), "distance": (0, 1),
                  "sensitivity": (0, 5), "threshold": (0, 0.99), "attack": (0, 1), "decay": (0.01, 2),
                  "beat_every": (1, 16), "beat_phase": (0, 15), "react_outline": (0, 0.05),
                  "react_scale": (0, 1), "react_x": (-0.5, 0.5), "react_y": (-0.5, 0.5),
                  "react_opacity": (0, 1), "react_shadow": (0, 0.1)}
        for name, bounds in ranges.items():
            number(item[name], name, *bounds)
        if item["end"] <= item["start"]:
            raise ValueError(f"Layer {i + 1}: end must be after start.")
        if type(item["beat_every"]) is not int or type(item["beat_phase"]) is not int:
            raise ValueError("Beat interval and phase must be whole numbers.")
        for name in ("color", "stroke_color", "shadow_color", "block_color"):
            color(item[name], name)
        curve = item["curve"]
        if not isinstance(curve, list) or len(curve) != 4:
            raise ValueError("Custom easing needs four Bezier control values.")
        for v in curve:
            number(v, "Bezier control", 0, 1)
        keys = item["keyframes"]
        if not isinstance(keys, list) or len(keys) > 200:
            raise ValueError("Use at most 200 keyframes per layer.")
        previous = -1
        for key in keys:
            if not isinstance(key, dict) or set(key) != {"time", "x", "y", "scale", "rotation", "opacity"}:
                raise ValueError("Each keyframe needs time, x, y, scale, rotation and opacity.")
            number(key["time"], "keyframe time", item["start"], item["end"])
            if key["time"] <= previous:
                raise ValueError("Keyframe times must be strictly increasing.")
            previous = key["time"]
            for name in ("x", "y", "scale", "rotation", "opacity"):
                number(key[name], name, *ranges[name])
    return p


def validate_analysis(a):
    if not isinstance(a, dict) or a.get("version") != 1 or a.get("rate") != 60:
        raise ValueError("Unsupported audio analysis. Analyze the soundtrack again.")
    if not isinstance(a.get("file"), str) or not re.fullmatch(r"[a-f0-9]{64}", a.get("fingerprint", "")):
        raise ValueError("Invalid audio analysis identity.")
    number(a.get("duration"), "analysis duration", 0.01, 600)
    number(a.get("bpm"), "detected BPM", 0, 600)
    def sequence(values, limit, maximum, ordered=False):
        if not isinstance(values, list) or len(values) > limit:
            raise ValueError("Audio analysis exceeds its data limit.")
        previous = -1
        for value in values:
            number(value, "audio sample", 0, maximum)
            if ordered and value <= previous:
                raise ValueError("Audio events must be strictly increasing.")
            previous = value
    sequence(a.get("waveform"), 2400, 1)
    sequence(a.get("beats"), 12000, a["duration"], True)
    channels = a.get("channels")
    if not isinstance(channels, dict) or not channels or set(channels) - set(SOURCES):
        raise ValueError("Invalid analyzed sources.")
    for channel in channels.values():
        if not isinstance(channel, dict):
            raise ValueError("Invalid analyzed channel.")
        sequence(channel.get("levels"), 36001, 1)
        sequence(channel.get("hits"), 12000, a["duration"], True)
