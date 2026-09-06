from __future__ import annotations

import pytest

from mscha2v.core.schedule import compile_shot_plan
from mscha2v.core.schemas import (
    BeatMap,
    Block,
    Schedule,
    SchemaError,
    block_from_dict,
    block_to_dict,
    schedule_from_dict,
    schedule_from_json,
    schedule_to_dict,
    schedule_to_json,
    shot_plan_from_json,
    shot_plan_to_json,
    validate_block,
    validate_schedule,
)


def _beat_map(**overrides) -> BeatMap:
    kwargs = dict(
        duration_sec=10.0,
        sr=44100,
        bpm=120.0,
        beats_sec=[0.5, 1.0, 1.5, 2.0],
        onsets_sec=[0.5, 1.0],
        downbeats_sec=[0.5],
        analysis_source="full",
        offset_ms=500.0,
    )
    kwargs.update(overrides)
    return BeatMap(**kwargs)


TAGGY_PROMPT = '<Picture 2> neon skyline, <Audio 1> synced beat\nline two "quoted" — émigré café ☾'


def _schedule_with_taggy_prompt() -> Schedule:
    beat_map = _beat_map()
    block = Block(
        id="b1",
        prompt=TAGGY_PROMPT,
        negative="blurry, low quality",
        start_beat=0.0,
        end_beat=4.0,
    )
    return Schedule(
        version=1,
        fps=24,
        total_frames=200,
        audio_path="song.wav",
        beat_map=beat_map,
        grid="every_beat",
        curve="linear",
        blocks=[block],
        master_seed=42,
    )


def test_block_round_trip_preserves_prompt_bytes():
    block = Block(id="b1", prompt=TAGGY_PROMPT, negative="", start_beat=0.0, end_beat=2.0)
    restored = block_from_dict(block_to_dict(block))
    assert restored.prompt == TAGGY_PROMPT
    assert restored == block


def test_schedule_json_round_trip_exact_equality():
    schedule = _schedule_with_taggy_prompt()
    text = schedule_to_json(schedule)
    restored = schedule_from_json(text)
    assert restored == schedule
    assert restored.blocks[0].prompt == TAGGY_PROMPT


def test_schedule_dict_round_trip():
    schedule = _schedule_with_taggy_prompt()
    restored = schedule_from_dict(schedule_to_dict(schedule))
    assert restored == schedule


def test_invalid_analysis_source_rejected():
    beat_map = _beat_map(analysis_source="bogus")
    with pytest.raises(SchemaError):
        schedule = Schedule(
            version=1, fps=24, total_frames=10, audio_path="a.wav", beat_map=beat_map,
            grid="every_beat", curve="linear", blocks=[], master_seed=0,
        )
        validate_schedule(schedule)


def test_wrong_version_rejected():
    schedule = _schedule_with_taggy_prompt()
    bad = schedule_to_dict(schedule)
    bad["version"] = 2
    with pytest.raises(SchemaError):
        schedule_from_dict(bad)


def test_missing_required_field_raises_clear_error():
    bad = schedule_to_dict(_schedule_with_taggy_prompt())
    del bad["fps"]
    with pytest.raises(SchemaError, match="fps"):
        schedule_from_dict(bad)


def test_invalid_grid_rejected():
    bad = schedule_to_dict(_schedule_with_taggy_prompt())
    bad["grid"] = "nonsense"
    with pytest.raises(SchemaError):
        schedule_from_dict(bad)


def test_start_beat_must_be_before_end_beat():
    block = Block(id="b1", prompt="x", negative="", start_beat=5.0, end_beat=5.0)
    with pytest.raises(SchemaError):
        validate_block(block)


def test_duplicate_block_ids_rejected():
    beat_map = _beat_map()
    b1 = Block(id="dup", prompt="a", negative="", start_beat=0.0, end_beat=1.0)
    b2 = Block(id="dup", prompt="b", negative="", start_beat=1.0, end_beat=2.0)
    schedule = Schedule(
        version=1, fps=24, total_frames=10, audio_path="a.wav", beat_map=beat_map,
        grid="every_beat", curve="linear", blocks=[b1, b2], master_seed=0,
    )
    with pytest.raises(SchemaError):
        validate_schedule(schedule)


def test_shot_plan_json_round_trip_preserves_cond_keyframe_prompts():
    schedule = _schedule_with_taggy_prompt()
    # Give the block real, grid-plausible frame bounds so compile_shot_plan succeeds.
    schedule = Schedule(
        version=schedule.version, fps=schedule.fps, total_frames=200,
        audio_path=schedule.audio_path, beat_map=schedule.beat_map, grid=schedule.grid,
        curve=schedule.curve,
        blocks=[
            Block(
                id="b1", prompt=TAGGY_PROMPT, negative="neg", start_beat=0.0, end_beat=4.0,
                start_frame=0, end_frame=150,
            )
        ],
        master_seed=schedule.master_seed,
    )
    plan = compile_shot_plan(schedule)
    text = shot_plan_to_json(plan)
    restored = shot_plan_from_json(text)
    assert restored.shots[0].cond_keyframes[0].prompt == TAGGY_PROMPT
    assert restored == plan
