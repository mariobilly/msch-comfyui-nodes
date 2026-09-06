from __future__ import annotations

import pytest

from mscha2v.core.buckets import BucketOverflowError
from mscha2v.core.schedule import ScheduleError, block_output_ranges, compile_shot_plan
from mscha2v.core.schemas import (
    BeatMap,
    Block,
    Schedule,
    schedule_from_json,
    schedule_to_json,
)

TAGGY_PROMPT = '<Picture 2> neon skyline, <Audio 1> synced beat\nsecond line "quoted" — émigré café ☾'

# bpm=1440 with an empty beats_sec array makes the beat_to_seconds fallback
# interval exactly 1/24s -- i.e. one "beat" unit == one frame at fps=24, so
# frame boundaries below are exact and easy to reason about in a test fixture.
_BEAT_MAP = BeatMap(
    duration_sec=520 / 24,
    sr=44100,
    bpm=1440.0,
    beats_sec=[],
    onsets_sec=[],
    downbeats_sec=[],
    analysis_source="full",
    offset_ms=0.0,
)


def _make_schedule(blocks: list[Block], total_frames: int = 520) -> Schedule:
    return Schedule(
        version=1,
        fps=24,
        total_frames=total_frames,
        audio_path="song.wav",
        beat_map=_BEAT_MAP,
        grid="every_beat",
        curve="linear",
        blocks=blocks,
        master_seed=42,
    )


def _base_fixture_blocks() -> list[Block]:
    return [
        Block(id="A", prompt="wide shot of a city", negative="blurry", start_beat=0, end_beat=130),
        Block(id="B", prompt="crowd dancing", negative="blurry", start_beat=130, end_beat=260),
        Block(id="C1", prompt=TAGGY_PROMPT, negative="low quality", start_beat=260, end_beat=330, group_id="g1"),
        Block(id="C2", prompt="camera pulls back", negative="low quality", start_beat=330, end_beat=400, group_id="g1"),
        Block(id="D", prompt="fireworks finale", negative="blurry", start_beat=400, end_beat=520),
    ]


def test_compile_shot_plan_kinds_and_frames():
    schedule = _make_schedule(_base_fixture_blocks())
    plan = compile_shot_plan(schedule)

    assert [s.kind for s in plan.shots] == ["single", "single", "group", "single"]
    assert [len(s.blocks) for s in plan.shots] == [1, 1, 2, 1]

    a, b, g1, d = plan.shots
    assert (a.n_frames, a.bucket_frames, a.trim_tail) == (130, 141, 11)
    assert (b.n_frames, b.bucket_frames, b.trim_tail) == (130, 141, 11)
    assert (g1.n_frames, g1.bucket_frames, g1.trim_tail) == (140, 141, 1)
    assert (d.n_frames, d.bucket_frames, d.trim_tail) == (120, 124, 4)


def test_compile_shot_plan_seeds():
    schedule = _make_schedule(_base_fixture_blocks())
    plan = compile_shot_plan(schedule)
    assert [s.seed for s in plan.shots] == [42, 43, 44, 45]

    # An explicit block-level override on a single's block wins outright.
    blocks = _base_fixture_blocks()
    blocks[1] = Block(
        id="B", prompt="crowd dancing", negative="blurry", start_beat=130, end_beat=260, seed=999,
    )
    plan2 = compile_shot_plan(_make_schedule(blocks))
    assert plan2.shots[1].seed == 999


def test_compile_shot_plan_is_deterministic():
    schedule = _make_schedule(_base_fixture_blocks())
    plan1 = compile_shot_plan(schedule)
    plan2 = compile_shot_plan(schedule)
    assert plan1 == plan2


def test_group_cond_keyframes_relative_frames_and_verbatim_prompts():
    schedule = _make_schedule(_base_fixture_blocks())
    plan = compile_shot_plan(schedule)
    group_shot = plan.shots[2]
    assert [kf.frame for kf in group_shot.cond_keyframes] == [0, 70]
    assert group_shot.cond_keyframes[0].prompt == TAGGY_PROMPT


def test_prompt_survives_full_json_round_trip_then_compile():
    # The whole pipeline (author -> serialize -> deserialize -> compile) must
    # preserve prompt bytes exactly, not just a direct in-memory call.
    schedule = _make_schedule(_base_fixture_blocks())
    text = schedule_to_json(schedule)
    restored_schedule = schedule_from_json(text)
    plan = compile_shot_plan(restored_schedule)
    group_shot = plan.shots[2]
    assert group_shot.cond_keyframes[0].prompt == TAGGY_PROMPT
    assert group_shot.blocks[0].prompt == TAGGY_PROMPT


def test_non_contiguous_group_id_raises():
    # Same group_id reused for two runs with an ungrouped block wedged
    # between them in timeline order -- not a valid single contiguous group.
    blocks = [
        Block(id="C1", prompt="a", negative="", start_beat=0, end_beat=50, group_id="g1"),
        Block(id="X", prompt="b", negative="", start_beat=50, end_beat=100),
        Block(id="C2", prompt="c", negative="", start_beat=100, end_beat=150, group_id="g1"),
    ]
    with pytest.raises(ScheduleError):
        compile_shot_plan(_make_schedule(blocks, total_frames=150))


def test_overlapping_group_gap_raises():
    blocks = [
        Block(id="C1", prompt="a", negative="", start_beat=0, end_beat=50, group_id="g1"),
        Block(id="C2", prompt="b", negative="", start_beat=60, end_beat=100, group_id="g1"),  # 10-frame gap
    ]
    with pytest.raises(ScheduleError):
        compile_shot_plan(_make_schedule(blocks, total_frames=100))


def test_block_output_ranges_span_total_frames():
    schedule = _make_schedule(_base_fixture_blocks())
    plan = compile_shot_plan(schedule)
    ranges = block_output_ranges(plan)
    assert [r[0] for r in ranges] == ["A", "B", "C1", "C2", "D"]
    assert ranges[0][1] == 0
    assert ranges[-1][2] == plan.total_frames == 520
    # No crossfade configured in this fixture -> perfectly contiguous.
    # Intentionally offset pairwise iteration (ranges vs ranges[1:]) -- these
    # are naturally different lengths, so strict=False (not True) is correct.
    for (_, _, end), (_, next_start, _) in zip(ranges, ranges[1:], strict=False):
        assert end == next_start


def test_block_spanning_beyond_max_trained_frames_raises_bucket_overflow():
    blocks = [Block(id="huge", prompt="p", negative="", start_beat=0, end_beat=400)]
    with pytest.raises(BucketOverflowError):
        compile_shot_plan(_make_schedule(blocks, total_frames=400))


def test_empty_schedule_compiles_to_empty_plan():
    schedule = _make_schedule([], total_frames=0)
    plan = compile_shot_plan(schedule)
    assert plan.shots == []
    assert plan.total_frames == 0
