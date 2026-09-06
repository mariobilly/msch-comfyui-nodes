"""Compiles a Schedule (beat-space blocks authored in the sequencer UI) into a
ShotPlan (frame-accurate render units ready for MschA2V_BeatKSampler).

Zero ComfyUI/torch imports.
"""

from __future__ import annotations

import dataclasses

from . import buckets, drift
from .schemas import (
    BeatMap,
    Block,
    CondKeyframe,
    Schedule,
    Shot,
    ShotPlan,
    validate_block,
    validate_schedule,
)


class ScheduleError(ValueError):
    """Raised when a Schedule cannot be compiled into a valid ShotPlan."""


def _beat_to_seconds(beat_map: BeatMap, beat_index: float) -> float:
    """Map a (possibly fractional) beat index onto a real timestamp in seconds.

    `start_beat`/`end_beat` are positions in the *detected* beat grid
    (`beat_map.beats_sec`), not a purely mathematical bpm*t formula -- real
    music drifts in tempo, and beat-syncing is only meaningful relative to
    where the beats actually are. Interpolates linearly between detected
    beats; extrapolates past either end using the nearest detected interval
    (or the bpm-derived interval if there's no second beat / no beats at all
    to measure an interval from).
    """
    beats = beat_map.beats_sec
    fallback_interval = 60.0 / beat_map.bpm if beat_map.bpm > 0 else 0.5

    if not beats:
        return beat_index * fallback_interval

    n = len(beats)
    if beat_index <= 0:
        interval = (beats[1] - beats[0]) if n > 1 else fallback_interval
        return beats[0] + beat_index * interval
    if beat_index >= n - 1:
        interval = (beats[-1] - beats[-2]) if n > 1 else fallback_interval
        return beats[-1] + (beat_index - (n - 1)) * interval

    lo = int(beat_index)
    frac = beat_index - lo
    return beats[lo] + frac * (beats[lo + 1] - beats[lo])


def _resolve_frame_boundaries(schedule: Schedule) -> dict[float, int]:
    """Drift-correct every block boundary ONCE across the whole timeline.

    Boundaries are collected from all blocks, deduplicated, converted to
    seconds, and run through drift.beats_to_frame_boundaries as a single
    monotonic sequence -- exactly what the drift-correction algorithm needs
    to guarantee no cumulative phase error, versus correcting each block
    independently (which would reintroduce the drift it's meant to prevent).
    """
    boundary_beats = sorted({b.start_beat for b in schedule.blocks} | {b.end_beat for b in schedule.blocks})
    boundary_secs = [_beat_to_seconds(schedule.beat_map, beat) for beat in boundary_beats]
    boundary_frames = drift.beats_to_frame_boundaries(boundary_secs, float(schedule.fps))
    return dict(zip(boundary_beats, boundary_frames, strict=True))


def _group_contiguous_blocks(resolved_blocks: list[Block]) -> list[list[Block]]:
    groups: list[list[Block]] = []
    i, n = 0, len(resolved_blocks)
    while i < n:
        block = resolved_blocks[i]
        if block.group_id is None:
            groups.append([block])
            i += 1
            continue
        run = [block]
        j = i + 1
        while j < n and resolved_blocks[j].group_id == block.group_id:
            if resolved_blocks[j].start_frame != run[-1].end_frame:
                raise ScheduleError(
                    f"group {block.group_id!r}: blocks must be frame-contiguous "
                    f"({run[-1].id!r} ends at frame {run[-1].end_frame}, "
                    f"{resolved_blocks[j].id!r} starts at frame {resolved_blocks[j].start_frame})"
                )
            run.append(resolved_blocks[j])
            j += 1
        if any(rb.group_id == block.group_id for rb in resolved_blocks[j:]):
            raise ScheduleError(
                f"group {block.group_id!r}: all blocks sharing a group_id must be contiguous "
                "in the timeline (found a non-adjacent member)"
            )
        groups.append(run)
        i = j
    return groups


def compile_shot_plan(schedule: Schedule) -> ShotPlan:
    """Compile a Schedule into a ShotPlan.

    - Recomputes every block's start_frame/end_frame from its authoritative
      start_beat/end_beat via a single whole-timeline drift correction
      (core/drift.py) -- any start_frame/end_frame already present on the
      incoming Block is discarded, since beat-space is authoritative.
    - Groups contiguous same-group_id blocks into one "group" Shot each;
      every other block becomes its own "single" Shot.
    - Solves each shot's H3 render-length bucket (core/buckets.py).
    - Resolves each shot's seed and builds its cond_keyframes, copying
      prompt/negative text byte-for-byte (no trimming/reformatting/tag
      processing -- that only happens later, at render time, once ComfyUI
      and the H3 pack are available).
    """
    validate_schedule(schedule)
    if not schedule.blocks:
        return ShotPlan(shots=[], fps=schedule.fps, total_frames=0, audio_path=schedule.audio_path)

    blocks_sorted = sorted(schedule.blocks, key=lambda b: (b.start_beat, b.end_beat))
    beat_to_frame = _resolve_frame_boundaries(schedule)

    resolved_blocks = [
        dataclasses.replace(b, start_frame=beat_to_frame[b.start_beat], end_frame=beat_to_frame[b.end_beat])
        for b in blocks_sorted
    ]
    for b in resolved_blocks:
        validate_block(b, require_frames=True)

    groups = _group_contiguous_blocks(resolved_blocks)

    shots: list[Shot] = []
    for shot_index, group_blocks in enumerate(groups):
        n_frames = group_blocks[-1].end_frame - group_blocks[0].start_frame
        bucket_frames, trim_tail = buckets.solve_bucket(n_frames)

        head_override = group_blocks[0].seed
        seed = head_override if head_override is not None else (schedule.master_seed + shot_index) & 0xFFFFFFFF

        cond_keyframes = [
            CondKeyframe(
                frame=block.start_frame - group_blocks[0].start_frame,
                prompt=block.prompt,
                negative=block.negative,
            )
            for block in group_blocks
        ]

        shots.append(
            Shot(
                kind="group" if len(group_blocks) > 1 else "single",
                blocks=group_blocks,
                n_frames=n_frames,
                bucket_frames=bucket_frames,
                trim_tail=trim_tail,
                seed=seed,
                cond_keyframes=cond_keyframes,
            )
        )

    # schedule.total_frames is authored by the frontend's own JS port of the
    # beat->frame snapping algorithm (see web/sequencer/state.js) and is not
    # trusted here: it can drift by a frame from this module's Python-side
    # resolution above. Re-derive the true total from the same boundary math
    # (block_output_ranges) that MschA2V_ShotAssembler uses to build the
    # actual timeline, so planning and assembly can never disagree.
    provisional = ShotPlan(shots=shots, fps=schedule.fps, total_frames=0, audio_path=schedule.audio_path)
    ranges = block_output_ranges(provisional)
    resolved_total_frames = ranges[-1][2] if ranges else 0
    return dataclasses.replace(provisional, total_frames=resolved_total_frames)


def block_output_ranges(shot_plan: ShotPlan) -> list[tuple[str, int, int]]:
    """Return [(block_id, output_start_frame, output_end_frame), ...] for the
    final assembled timeline, in shot/block order.

    Shared by MschA2V_ShotAssembler and MschA2V_BeatPixelUpscaleKSampler so
    both use exactly the same boundary math (the assembler builds the
    timeline with it; the upscaler re-splits an already-assembled IMAGE
    batch back into per-block slices with it).

    Blocks within the same shot (i.e. within a group) are back-to-back with
    no overlap -- continuity there comes from generation-time first_frame
    conditioning, not post-hoc blending. Adjacent DIFFERENT shots overlap by
    `crossfade_frames`, read from the incoming (later) shot's head block, to
    represent the alpha-blended dissolve region the assembler renders there.
    """
    ranges: list[tuple[str, int, int]] = []
    cursor = 0
    for shot_index, shot in enumerate(shot_plan.shots):
        for block_index, block in enumerate(shot.blocks):
            length = block.end_frame - block.start_frame
            if block_index == 0 and shot_index > 0:
                overlap = min(block.crossfade_frames, length, cursor)
                cursor -= overlap
            start = cursor
            end = cursor + length
            ranges.append((block.id, start, end))
            cursor = end
    return ranges
