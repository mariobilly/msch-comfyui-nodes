import json

from slideshowforge.core import schema
from slideshowforge.core.timeline_builder import build_timeline


def _build(**overrides):
    kwargs = dict(
        image_count=5,
        preset_name="classic_ken_burns",
        duration_mode="total_duration",
        total_duration=20.0,
        per_image_duration=3.0,
        fps=30,
        seed=42,
    )
    kwargs.update(overrides)
    return build_timeline(**kwargs)


def test_determinism_same_seed_identical_output():
    a = _build()
    b = _build()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_different_seed_differs():
    a = _build(seed=1)
    b = _build(seed=2)
    assert json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)


def test_output_passes_schema_validation():
    for preset in ("classic_ken_burns", "dynamic_wipes", "slow_cinematic"):
        timeline = _build(preset_name=preset)
        errors = schema.validate_timeline(timeline)
        assert errors == [], f"{preset}: {errors}"


def test_single_image_has_no_transitions():
    timeline = _build(image_count=1)
    assert len(timeline["segments"]) == 1
    assert timeline["segments"][0]["transition_out"] is None
    errors = schema.validate_timeline(timeline)
    assert errors == []


def test_two_images_have_exactly_one_transition():
    timeline = _build(image_count=2)
    segments = timeline["segments"]
    assert len(segments) == 2
    assert segments[0]["transition_out"] is not None
    assert segments[1]["transition_out"] is None


def test_total_duration_mode_matches_target_within_reason():
    timeline = _build(image_count=6, total_duration=24.0)
    assert abs(timeline["total_duration"] - 24.0) < 1.0
    assert abs(timeline["duration_solve_residual"]) < 1.0


def test_per_image_duration_mode_uses_exact_durations():
    timeline = _build(image_count=4, duration_mode="per_image_duration", per_image_duration=2.5)
    for seg in timeline["segments"]:
        assert seg["duration"] == 2.5


def test_loop_adds_final_transition():
    timeline = _build(image_count=4, loop=True)
    assert timeline["segments"][-1]["transition_out"] is not None


def test_all_segment_durations_positive():
    timeline = _build(image_count=8, total_duration=15.0)
    for seg in timeline["segments"]:
        assert seg["duration"] > 0


def test_infeasible_total_duration_respects_preset_minimum():
    """Regression test: when total_duration is far below what this many
    segments can fit at the preset's minimum, every segment must clamp to
    that minimum rather than silently going under it (see the 26-image bug)."""
    timeline = _build(
        image_count=26, preset_name="dynamic_wipes", total_duration=15.0, seed=42
    )
    preset_min = 1.5  # dynamic_wipes segment_duration.min
    for seg in timeline["segments"]:
        assert seg["duration"] >= preset_min - 1e-9
    # Total must legitimately overshoot the infeasible target, not hit it.
    assert timeline["total_duration"] > 15.0
    assert timeline["duration_solve_residual"] < 0


def test_beat_sync_spans_full_audio_duration():
    """The timeline must cover the whole loaded audio clip, not just the span
    between the first and last detected beat -- a beatless intro/outro must
    be absorbed into the first/last segment's dwell time, never dropped."""
    beats_sec = [i * 0.5 for i in range(40)]  # 40 beats, 0.5s apart (120bpm)
    audio_duration_sec = 20.0
    timeline = _build(
        image_count=5, duration_mode="beat_sync", beats_sec=beats_sec,
        beats_per_image=2, audio_duration_sec=audio_duration_sec,
    )
    assert len(timeline["segments"]) == 5
    total = sum(s["duration"] for s in timeline["segments"])
    assert abs(total - audio_duration_sec) < 1e-9
    assert timeline["audio_sync"]["beats_per_image"] == 2
    errors = schema.validate_timeline(timeline)
    assert errors == []


def test_beat_sync_internal_cuts_land_on_real_beats():
    beats_sec = [i * 0.5 for i in range(40)]
    audio_duration_sec = 20.0
    timeline = _build(
        image_count=5, duration_mode="beat_sync", beats_sec=beats_sec,
        beats_per_image=2, audio_duration_sec=audio_duration_sec,
    )
    durations = [s["duration"] for s in timeline["segments"]]
    cumulative = 0.0
    for d in durations[:-1]:  # every boundary except the final one (= audio end) is a real beat
        cumulative += d
        assert any(abs(cumulative - b) < 1e-9 for b in beats_sec), cumulative


def test_beat_sync_uses_one_more_segment_than_available_full_groups():
    """With N beats and beats_per_image=k, floor(N/k) internal cuts are
    possible, which supports floor(N/k)+1 segments (the last segment needs
    no beat group of its own -- it just runs to the audio's end)."""
    beats_sec = [i * 0.5 for i in range(6)]  # 6 beats -> 3 internal-cut groups of 2
    timeline = _build(
        image_count=10, duration_mode="beat_sync", beats_sec=beats_sec,
        beats_per_image=2, audio_duration_sec=4.0,
    )
    assert len(timeline["segments"]) == 4


def test_beat_sync_degrades_to_one_segment_with_sparse_beats():
    timeline = _build(
        image_count=5, duration_mode="beat_sync", beats_sec=[1.0, 2.0],
        beats_per_image=8, audio_duration_sec=10.0,
    )
    assert len(timeline["segments"]) == 1
    assert abs(timeline["segments"][0]["duration"] - 10.0) < 1e-9


def test_beat_sync_raises_without_audio_analysis():
    try:
        _build(image_count=5, duration_mode="beat_sync", beats_sec=None, beats_per_image=2)
        assert False, "expected ValueError"
    except ValueError:
        pass
