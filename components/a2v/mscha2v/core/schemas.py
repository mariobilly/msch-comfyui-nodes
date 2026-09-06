"""Data contracts for MschA2V: BeatMap, Block, Schedule, CondKeyframe, Shot, ShotPlan.

Zero ComfyUI/torch imports -- stdlib only, so this module (and everything
else in mscha2v/core/) is importable and testable with plain pytest, no
ComfyUI install and no GPU required.

Prompt text is never trimmed, reformatted, or tag-stripped anywhere in this
module -- `json.dumps(..., ensure_ascii=False)` is used throughout so
non-ASCII prompt content survives serialization byte-for-byte.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

SCHEMA_VERSION = 1

ANALYSIS_SOURCES = ("full", "drums", "percussive")
GRIDS = ("every_beat", "half", "quarter", "bar")
CURVES = ("linear", "ease")
SHOT_KINDS = ("single", "group")


class SchemaError(ValueError):
    """Raised when a BeatMap/Block/Schedule/ShotPlan payload fails validation."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SchemaError(message)


def _require_keys(data: dict, keys: tuple[str, ...], where: str) -> None:
    _require(isinstance(data, dict), f"{where} must be an object, got {type(data).__name__}")
    for key in keys:
        _require(key in data, f"{where}.{key} is required")


# ---------------------------------------------------------------------------
# BeatMap
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BeatMap:
    duration_sec: float
    sr: int
    bpm: float
    beats_sec: list[float]
    onsets_sec: list[float]
    downbeats_sec: list[float]
    analysis_source: str
    offset_ms: float


def beat_map_to_dict(beat_map: BeatMap) -> dict:
    return {
        "duration_sec": beat_map.duration_sec,
        "sr": beat_map.sr,
        "bpm": beat_map.bpm,
        "beats_sec": list(beat_map.beats_sec),
        "onsets_sec": list(beat_map.onsets_sec),
        "downbeats_sec": list(beat_map.downbeats_sec),
        "analysis_source": beat_map.analysis_source,
        "offset_ms": beat_map.offset_ms,
    }


def beat_map_from_dict(data: dict) -> BeatMap:
    _require_keys(
        data,
        ("duration_sec", "sr", "bpm", "beats_sec", "onsets_sec", "downbeats_sec", "analysis_source", "offset_ms"),
        "beat_map",
    )
    beat_map = BeatMap(
        duration_sec=float(data["duration_sec"]),
        sr=int(data["sr"]),
        bpm=float(data["bpm"]),
        beats_sec=[float(x) for x in data["beats_sec"]],
        onsets_sec=[float(x) for x in data["onsets_sec"]],
        downbeats_sec=[float(x) for x in data["downbeats_sec"]],
        analysis_source=data["analysis_source"],
        offset_ms=float(data["offset_ms"]),
    )
    validate_beat_map(beat_map)
    return beat_map


def validate_beat_map(beat_map: BeatMap) -> None:
    _require(beat_map.duration_sec >= 0, "beat_map.duration_sec must be >= 0")
    _require(beat_map.sr > 0, "beat_map.sr must be > 0")
    _require(beat_map.bpm >= 0, "beat_map.bpm must be >= 0")
    _require(
        beat_map.analysis_source in ANALYSIS_SOURCES,
        f"beat_map.analysis_source must be one of {ANALYSIS_SOURCES}, got {beat_map.analysis_source!r}",
    )


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Block:
    id: str
    prompt: str
    negative: str
    start_beat: float
    end_beat: float
    start_frame: int = 0
    end_frame: int = 0
    fade_in_frames: int = 0
    fade_out_frames: int = 0
    crossfade_frames: int = 0
    group_id: str | None = None
    seed: int | None = None
    ref_image_slot: int | None = None
    ref_audio_slot: int | None = None


def block_to_dict(block: Block) -> dict:
    return {
        "id": block.id,
        "prompt": block.prompt,
        "negative": block.negative,
        "start_beat": block.start_beat,
        "end_beat": block.end_beat,
        "start_frame": block.start_frame,
        "end_frame": block.end_frame,
        "fade_in_frames": block.fade_in_frames,
        "fade_out_frames": block.fade_out_frames,
        "crossfade_frames": block.crossfade_frames,
        "group_id": block.group_id,
        "seed": block.seed,
        "ref_image_slot": block.ref_image_slot,
        "ref_audio_slot": block.ref_audio_slot,
    }


def block_from_dict(data: dict) -> Block:
    _require_keys(data, ("id", "prompt", "negative", "start_beat", "end_beat"), "block")
    block = Block(
        id=str(data["id"]),
        prompt=str(data["prompt"]),
        negative=str(data["negative"]),
        start_beat=float(data["start_beat"]),
        end_beat=float(data["end_beat"]),
        start_frame=int(data.get("start_frame", 0)),
        end_frame=int(data.get("end_frame", 0)),
        fade_in_frames=int(data.get("fade_in_frames", 0)),
        fade_out_frames=int(data.get("fade_out_frames", 0)),
        crossfade_frames=int(data.get("crossfade_frames", 0)),
        group_id=data.get("group_id"),
        seed=(int(data["seed"]) if data.get("seed") is not None else None),
        ref_image_slot=(int(data["ref_image_slot"]) if data.get("ref_image_slot") is not None else None),
        ref_audio_slot=(int(data["ref_audio_slot"]) if data.get("ref_audio_slot") is not None else None),
    )
    validate_block(block)
    return block


def validate_block(block: Block, *, require_frames: bool = False) -> None:
    _require(bool(block.id), "block.id must be non-empty")
    _require(isinstance(block.prompt, str), "block.prompt must be a string")
    _require(isinstance(block.negative, str), "block.negative must be a string")
    _require(block.start_beat < block.end_beat, f"block {block.id!r}: start_beat must be < end_beat")
    _require(block.fade_in_frames >= 0, f"block {block.id!r}: fade_in_frames must be >= 0")
    _require(block.fade_out_frames >= 0, f"block {block.id!r}: fade_out_frames must be >= 0")
    _require(block.crossfade_frames >= 0, f"block {block.id!r}: crossfade_frames must be >= 0")
    _require(
        block.group_id is None or isinstance(block.group_id, str),
        f"block {block.id!r}: group_id must be a string or null",
    )
    if require_frames:
        _require(
            block.start_frame < block.end_frame,
            f"block {block.id!r}: start_frame must be < end_frame once compiled",
        )


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Schedule:
    version: int
    fps: int
    total_frames: int
    audio_path: str
    beat_map: BeatMap
    grid: str
    curve: str
    blocks: list[Block] = field(default_factory=list)
    master_seed: int = 0


def schedule_to_dict(schedule: Schedule) -> dict:
    return {
        "version": schedule.version,
        "fps": schedule.fps,
        "total_frames": schedule.total_frames,
        "audio_path": schedule.audio_path,
        "beat_map": beat_map_to_dict(schedule.beat_map),
        "grid": schedule.grid,
        "curve": schedule.curve,
        "blocks": [block_to_dict(b) for b in schedule.blocks],
        "master_seed": schedule.master_seed,
    }


def schedule_from_dict(data: dict) -> Schedule:
    _require_keys(
        data,
        ("version", "fps", "total_frames", "audio_path", "beat_map", "grid", "curve", "blocks", "master_seed"),
        "schedule",
    )
    schedule = Schedule(
        version=int(data["version"]),
        fps=int(data["fps"]),
        total_frames=int(data["total_frames"]),
        audio_path=str(data["audio_path"]),
        beat_map=beat_map_from_dict(data["beat_map"]),
        grid=data["grid"],
        curve=data["curve"],
        blocks=[block_from_dict(b) for b in data["blocks"]],
        master_seed=int(data["master_seed"]),
    )
    validate_schedule(schedule)
    return schedule


def schedule_to_json(schedule: Schedule) -> str:
    return json.dumps(schedule_to_dict(schedule), ensure_ascii=False)


def schedule_from_json(text: str) -> Schedule:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"schedule_json is not valid JSON: {exc}") from exc
    return schedule_from_dict(data)


def validate_schedule(schedule: Schedule) -> None:
    _require(schedule.version == SCHEMA_VERSION, f"schedule.version must be {SCHEMA_VERSION}, got {schedule.version}")
    _require(schedule.fps > 0, "schedule.fps must be > 0")
    _require(schedule.total_frames >= 0, "schedule.total_frames must be >= 0")
    _require(isinstance(schedule.audio_path, str), "schedule.audio_path must be a string")
    _require(schedule.grid in GRIDS, f"schedule.grid must be one of {GRIDS}, got {schedule.grid!r}")
    _require(schedule.curve in CURVES, f"schedule.curve must be one of {CURVES}, got {schedule.curve!r}")
    validate_beat_map(schedule.beat_map)
    ids_seen: set[str] = set()
    for block in schedule.blocks:
        validate_block(block)
        _require(block.id not in ids_seen, f"duplicate block id {block.id!r}")
        ids_seen.add(block.id)


# ---------------------------------------------------------------------------
# ShotPlan (CondKeyframe, Shot, ShotPlan)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CondKeyframe:
    frame: int
    prompt: str
    negative: str


def cond_keyframe_to_dict(kf: CondKeyframe) -> dict:
    return {"frame": kf.frame, "prompt": kf.prompt, "negative": kf.negative}


def cond_keyframe_from_dict(data: dict) -> CondKeyframe:
    _require_keys(data, ("frame", "prompt", "negative"), "cond_keyframe")
    return CondKeyframe(frame=int(data["frame"]), prompt=str(data["prompt"]), negative=str(data["negative"]))


@dataclass(frozen=True)
class Shot:
    kind: str
    blocks: list[Block]
    n_frames: int
    bucket_frames: int
    trim_tail: int
    seed: int
    cond_keyframes: list[CondKeyframe]


def shot_to_dict(shot: Shot) -> dict:
    return {
        "kind": shot.kind,
        "blocks": [block_to_dict(b) for b in shot.blocks],
        "n_frames": shot.n_frames,
        "bucket_frames": shot.bucket_frames,
        "trim_tail": shot.trim_tail,
        "seed": shot.seed,
        "cond_keyframes": [cond_keyframe_to_dict(k) for k in shot.cond_keyframes],
    }


def shot_from_dict(data: dict) -> Shot:
    _require_keys(data, ("kind", "blocks", "n_frames", "bucket_frames", "trim_tail", "seed", "cond_keyframes"), "shot")
    shot = Shot(
        kind=data["kind"],
        blocks=[block_from_dict(b) for b in data["blocks"]],
        n_frames=int(data["n_frames"]),
        bucket_frames=int(data["bucket_frames"]),
        trim_tail=int(data["trim_tail"]),
        seed=int(data["seed"]),
        cond_keyframes=[cond_keyframe_from_dict(k) for k in data["cond_keyframes"]],
    )
    validate_shot(shot)
    return shot


def validate_shot(shot: Shot) -> None:
    _require(shot.kind in SHOT_KINDS, f"shot.kind must be one of {SHOT_KINDS}, got {shot.kind!r}")
    _require(len(shot.blocks) > 0, "shot.blocks must be non-empty")
    if shot.kind == "single":
        _require(len(shot.blocks) == 1, "a 'single' shot must contain exactly one block")
    else:
        _require(len(shot.blocks) >= 2, "a 'group' shot must contain at least two blocks")
    _require(shot.n_frames > 0, "shot.n_frames must be > 0")
    _require(shot.bucket_frames >= shot.n_frames, "shot.bucket_frames must be >= shot.n_frames")
    _require(
        shot.trim_tail == shot.bucket_frames - shot.n_frames,
        "shot.trim_tail must equal bucket_frames - n_frames",
    )
    _require(
        len(shot.cond_keyframes) == len(shot.blocks),
        "shot.cond_keyframes must have one entry per block",
    )
    for block, kf in zip(shot.blocks, shot.cond_keyframes, strict=True):
        _require(kf.prompt == block.prompt, f"cond_keyframe prompt for block {block.id!r} must match the block verbatim")
        _require(
            kf.negative == block.negative,
            f"cond_keyframe negative for block {block.id!r} must match the block verbatim",
        )


@dataclass(frozen=True)
class ShotPlan:
    shots: list[Shot]
    fps: int
    total_frames: int
    audio_path: str


def shot_plan_to_dict(plan: ShotPlan) -> dict:
    return {
        "shots": [shot_to_dict(s) for s in plan.shots],
        "fps": plan.fps,
        "total_frames": plan.total_frames,
        "audio_path": plan.audio_path,
    }


def shot_plan_from_dict(data: dict) -> ShotPlan:
    _require_keys(data, ("shots", "fps", "total_frames", "audio_path"), "shot_plan")
    plan = ShotPlan(
        shots=[shot_from_dict(s) for s in data["shots"]],
        fps=int(data["fps"]),
        total_frames=int(data["total_frames"]),
        audio_path=str(data["audio_path"]),
    )
    validate_shot_plan(plan)
    return plan


def shot_plan_to_json(plan: ShotPlan) -> str:
    return json.dumps(shot_plan_to_dict(plan), ensure_ascii=False)


def shot_plan_from_json(text: str) -> ShotPlan:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"shot_plan JSON is not valid: {exc}") from exc
    return shot_plan_from_dict(data)


def validate_shot_plan(plan: ShotPlan) -> None:
    _require(plan.fps > 0, "shot_plan.fps must be > 0")
    _require(plan.total_frames >= 0, "shot_plan.total_frames must be >= 0")
    _require(isinstance(plan.audio_path, str), "shot_plan.audio_path must be a string")
    for shot in plan.shots:
        validate_shot(shot)
