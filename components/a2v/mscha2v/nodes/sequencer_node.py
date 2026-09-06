"""MschA2V_BeatPromptSequencer: the entry-point node. Holds the beat-synced
Schedule authored in the frontend Sequencer modal (mscha2v.js /
sequencer/*.js), stored as JSON in the hidden `schedule_json` widget.
"""

from __future__ import annotations

import hashlib
import logging
import os

from ..core import schemas
from ..core.schedule import compile_shot_plan
from ._common import load_audio_dict, resolve_audio_path


def _empty_schedule(audio_path: str) -> schemas.Schedule:
    empty_beat_map = schemas.BeatMap(
        duration_sec=0.0,
        sr=44100,
        bpm=0.0,
        beats_sec=[],
        onsets_sec=[],
        downbeats_sec=[],
        analysis_source="full",
        offset_ms=0.0,
    )
    return schemas.Schedule(
        version=schemas.SCHEMA_VERSION,
        fps=24,
        total_frames=0,
        audio_path=audio_path,
        beat_map=empty_beat_map,
        grid="every_beat",
        curve="linear",
        blocks=[],
        master_seed=0,
    )


class MschA2V_BeatPromptSequencer:
    """Opens the beat-synced prompt Sequencer (frontend "Open Sequencer"
    button) and outputs the compiled Schedule, the loaded song AUDIO, its
    detected BPM, and the timeline's total_frames.
    """

    CATEGORY = "MschA2V"
    FUNCTION = "run"
    RETURN_TYPES = ("MSCHA2V_SCHEDULE", "INT", "AUDIO", "FLOAT")
    RETURN_NAMES = ("prompt_schedule", "total_frames", "audio", "bpm")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_path": ("STRING", {"default": ""}),
                # Hidden by web/mscha2v.js (widget.computeSize = () => [0,-4]);
                # written by the Sequencer modal's Done button, read here.
                "schedule_json": ("STRING", {"multiline": True, "default": "{}"}),
            },
            "optional": {
                # -1 (default) = auto: derive from the schedule's own blocks
                # so the AUDIO output always stays frame-accurate to the
                # assembled video, with no action needed. Override either
                # one to trim to a specific window instead (e.g. to include
                # a few seconds of lead-in silence, or to use a source track
                # much longer than the authored blocks).
                "audio_start_seconds": ("FLOAT", {"default": -1.0, "min": -1.0, "max": 100000.0, "step": 0.01}),
                "audio_duration_seconds": ("FLOAT", {"default": -1.0, "min": -1.0, "max": 100000.0, "step": 0.01}),
            },
        }

    def run(
        self,
        audio_path: str,
        schedule_json: str,
        audio_start_seconds: float = -1.0,
        audio_duration_seconds: float = -1.0,
    ):
        schedule = self._load_schedule(schedule_json, audio_path)
        audio = load_audio_dict(schedule.audio_path or audio_path)

        # schedule.total_frames/block.start_frame come from the frontend's own
        # JS port of the beat->frame snapping algorithm and can drift by a
        # frame from this package's Python-side resolution (core/drift.py) --
        # the same resolution MschA2V_ShotPlanner/ShotAssembler use to build
        # the actual rendered timeline. Recompile here so the AUDIO window
        # and the total_frames output always agree with what will actually
        # be rendered, not with the frontend's estimate.
        try:
            plan = compile_shot_plan(schedule)
        except Exception:
            plan = None

        total_frames = plan.total_frames if plan is not None else schedule.total_frames

        start_seconds = audio_start_seconds
        if start_seconds < 0:
            fps = schedule.fps or 24
            if plan is not None and plan.shots:
                first_frame = plan.shots[0].blocks[0].start_frame
            elif schedule.blocks:
                first_frame = schedule.blocks[0].start_frame
            else:
                first_frame = 0
            start_seconds = first_frame / fps

        duration_seconds = audio_duration_seconds
        if duration_seconds < 0:
            fps = schedule.fps or 24
            duration_seconds = (total_frames / fps) if total_frames else 0.0

        if duration_seconds > 0:
            audio = self._window_audio(audio, start_seconds, duration_seconds)

        return (schedule, total_frames, audio, schedule.beat_map.bpm)

    @staticmethod
    def _window_audio(audio: dict, start_seconds: float, duration_seconds: float) -> dict:
        """Slice `audio` to [start_seconds, start_seconds + duration_seconds),
        zero-padding if the source is shorter than the requested window --
        keeps the AUDIO output exactly the length the video expects even if
        the source track runs out early.
        """
        import torch

        waveform = audio["waveform"]
        sr = audio["sample_rate"]
        start_sample = max(0, round(start_seconds * sr))
        num_samples = max(0, round(duration_seconds * sr))
        total_samples = waveform.shape[-1]

        if start_sample >= total_samples:
            sliced = torch.zeros((*waveform.shape[:-1], num_samples), dtype=waveform.dtype)
        else:
            sliced = waveform[..., start_sample : start_sample + num_samples]
            if sliced.shape[-1] < num_samples:
                pad = torch.zeros((*waveform.shape[:-1], num_samples - sliced.shape[-1]), dtype=waveform.dtype)
                sliced = torch.cat([sliced, pad], dim=-1)

        return {"waveform": sliced, "sample_rate": sr}

    @staticmethod
    def _load_schedule(schedule_json: str, audio_path: str) -> schemas.Schedule:
        text = (schedule_json or "").strip()
        if not text or text == "{}":
            logging.warning(
                "MschA2V_BeatPromptSequencer: schedule_json is empty. Open the Sequencer "
                "(button on this node) and click Done at least once before rendering. "
                "Using an empty placeholder Schedule for now so the graph doesn't hard-fail."
            )
            return _empty_schedule(audio_path)
        return schemas.schedule_from_json(text)

    @classmethod
    def IS_CHANGED(cls, audio_path, schedule_json, **kwargs):
        try:
            mtime = os.path.getmtime(resolve_audio_path(audio_path))
        except Exception:
            mtime = 0.0
        digest = hashlib.sha256()
        digest.update((schedule_json or "").encode("utf-8"))
        digest.update(str(mtime).encode("utf-8"))
        return digest.hexdigest()


NODE_CLASS_MAPPINGS = {
    "MschA2V_BeatPromptSequencer": MschA2V_BeatPromptSequencer,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MschA2V_BeatPromptSequencer": "MschA2V Beat Prompt Sequencer",
}
