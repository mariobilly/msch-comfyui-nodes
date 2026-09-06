"""MschA2V_ShotPlanner: compiles the beat-synced Schedule into frame-accurate
shots AND builds every block's H3 conditioning + starting (empty/audio-
locked) latent up front. This is where clip/vae/audio_vae/audio and any
global reference media live -- matching a reference MiniMax H3 beat-sync
workflow topology the user showed mid-session, where the planner (not the
sampler) owns conditioning. Input names below are matched 1:1 to that
reference node where the target is a real, confirmed H3 pack parameter
(clip/vae/audio_vae, prompt_schedule, timeline_audio, ref_image_0/1/2,
ref_video_0, ref_video_audio_0, ref_audio_0, ref_image_size) -- see
DECISIONS.md deviation #3 for the couple of intentional naming differences
(audio_mode instead of "affect_audio": same underlying H3 audio_mode values,
just not renamed since the "affect_audio" semantics weren't confirmed;
"prompt_envelope_0" from the reference is not implemented -- its purpose is
unknown, deliberately skipped rather than guessed).

MschA2V_BeatKSampler only needs `model` + this node's output + standard
sampler params.

Output is a single evolving "shot_plan" object (an opaque, node-only Python
dict under the MSCHA2V_SHOT_PLAN custom type) that flows through
BeatKSampler (fills in sampled latents), ShotAssembler (decodes/trims/fades/
concatenates), and BeatPixelUpscaleKSampler (re-samples at a higher
resolution). This is NOT the same object as mscha2v.core.schemas.ShotPlan,
which stays a pure, torch-free, JSON-serializable planning record used
internally here (compile_shot_plan) and by pytest.
"""

from __future__ import annotations

import dataclasses

from ..core.schedule import compile_shot_plan


class MschA2V_ShotPlanner:
    CATEGORY = "MschA2V"
    FUNCTION = "plan"
    RETURN_TYPES = ("MSCHA2V_SHOT_PLAN",)
    RETURN_NAMES = ("shot_plan",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_schedule": ("MSCHA2V_SCHEDULE",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "audio_vae": ("VAE",),
                "timeline_audio": ("AUDIO",),
                "master_seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
                "width": ("INT", {"default": 768, "min": 32, "max": 1920, "step": 32}),
                "height": ("INT", {"default": 768, "min": 32, "max": 1920, "step": 32}),
                "fps_override": ("INT", {"default": 0, "min": 0, "max": 60}),
                "audio_mode": (["lock_source", "remix_source", "native"], {"default": "lock_source"}),
                "task_type": (["auto", "t2va", "i2va", "fl2va", "l2va", "ref2va", "hybrid"], {"default": "auto"}),
                "add_source_as_reference": ("BOOLEAN", {"default": True}),
                "ref_image_size": (["match", "max"], {"default": "match"}),
            },
            "optional": {
                # Used only for blocks/cond_keyframes whose own `negative` is
                # empty -- each block's own negative prompt otherwise wins.
                "negative_fallback": ("STRING", {"multiline": True, "default": ""}),
                # Global reference media, applied to EVERY block for
                # identity/style consistency across the whole video (not
                # per-block frame-to-frame continuity). Maps directly onto
                # h3 conditioning.build_conditioning's ref_images/ref_videos/
                # ref_video_audios/ref_audios lists.
                "ref_image_0": ("IMAGE",),
                "ref_image_1": ("IMAGE",),
                "ref_image_2": ("IMAGE",),
                "ref_video_0": ("IMAGE",),
                "ref_video_audio_0": ("AUDIO",),
                "ref_audio_0": ("AUDIO",),
            },
        }

    def plan(
        self,
        prompt_schedule,
        clip,
        vae,
        audio_vae,
        timeline_audio,
        master_seed,
        width,
        height,
        fps_override,
        audio_mode,
        task_type,
        add_source_as_reference,
        ref_image_size,
        negative_fallback="",
        ref_image_0=None,
        ref_image_1=None,
        ref_image_2=None,
        ref_video_0=None,
        ref_video_audio_0=None,
        ref_audio_0=None,
    ):
        from ..h3 import adapter as h3adapter

        if width % 32 or height % 32:
            raise ValueError(f"MschA2V_ShotPlanner: width/height must be divisible by 32, got {width}x{height}")

        schedule = prompt_schedule
        audio = timeline_audio
        video_vae = vae

        effective = schedule
        overrides = {}
        if master_seed != schedule.master_seed:
            overrides["master_seed"] = master_seed
        if fps_override and fps_override != schedule.fps:
            overrides["fps"] = fps_override
        if overrides:
            effective = dataclasses.replace(schedule, **overrides)

        plan = compile_shot_plan(effective)

        ref_images = [img for img in (ref_image_0, ref_image_1, ref_image_2) if img is not None] or None
        ref_videos = [ref_video_0] if ref_video_0 is not None else None
        ref_video_audios = [ref_video_audio_0] if ref_video_audio_0 is not None else None
        ref_audios = [ref_audio_0] if ref_audio_0 is not None else None

        fps = float(plan.fps)
        full_song_duration_seconds = float(audio["waveform"].shape[-1]) / float(audio["sample_rate"])

        blocks_out = []
        for shot in plan.shots:
            for block_index, block in enumerate(shot.blocks):
                cond_kf = shot.cond_keyframes[block_index]
                block_len_frames = block.end_frame - block.start_frame

                timing_plan = h3adapter.plan_shot_timing(
                    scene_start_seconds=block.start_frame / fps,
                    scene_duration_seconds=block_len_frames / fps,
                    source_duration_seconds=full_song_duration_seconds,
                )
                windowed_audio = h3adapter.window_audio(audio, timing_plan)

                positive, av_latent, _mux_audio, _conditioned_prompt, _media_map, _report = h3adapter.build_conditioning(
                    clip,
                    video_vae,
                    audio_vae,
                    prompt=cond_kf.prompt,
                    width=width,
                    height=height,
                    length=timing_plan.frame_count,
                    task_type=task_type,
                    audio_mode=audio_mode,
                    add_source_as_reference=add_source_as_reference,
                    drive_audio=windowed_audio,
                    ref_images=ref_images,
                    ref_videos=ref_videos,
                    ref_video_audios=ref_video_audios,
                    ref_audios=ref_audios,
                    ref_image_size=ref_image_size,
                )

                negative_text = cond_kf.negative if cond_kf.negative else negative_fallback
                negative = clip.encode_from_tokens_scheduled(clip.tokenize(negative_text or ""))

                blocks_out.append(
                    {
                        "block_id": block.id,
                        "group_id": block.group_id,
                        "is_group_head": block_index == 0,
                        "is_group_tail": block_index == len(shot.blocks) - 1,
                        "positive": positive,
                        "negative": negative,
                        "av_latent": av_latent,
                        "seed_override": block.seed,
                        "timing_plan": timing_plan,
                        "block_len_frames": block_len_frames,
                        "fps": fps,
                        "fade_in_frames": block.fade_in_frames,
                        "fade_out_frames": block.fade_out_frames,
                        "crossfade_frames": block.crossfade_frames,
                    }
                )

        shot_plan = {
            "fps": fps,
            "total_frames": plan.total_frames,
            "audio_path": plan.audio_path,
            "blocks": blocks_out,
        }
        return (shot_plan,)


NODE_CLASS_MAPPINGS = {"MschA2V_ShotPlanner": MschA2V_ShotPlanner}
NODE_DISPLAY_NAME_MAPPINGS = {"MschA2V_ShotPlanner": "MschA2V Shot Planner"}
