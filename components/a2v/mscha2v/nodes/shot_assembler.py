"""MschA2V_ShotAssembler: decodes each block's sampled latent (from
MSCHA2V_LATENTS), trims padding, applies fades/crossfades, and concatenates
into the final IMAGE batch.

Deliberately minimal inputs (latents + vae only) -- matches a reference
MiniMax H3 beat-sync workflow topology the user showed mid-session. Only the
VIDEO branch is ever decoded here (mscha2v.h3.adapter.decode_video_only, no
audio_vae needed at all): the final AUDIO for the rendered video is always
the original loaded song track, wired directly from
MschA2V_BeatPromptSequencer (or MschA2V_LoadAudioPath) straight into your
video-combine node, never reassembled from decoded per-shot generated audio
-- this sidesteps VAE audio round-trip artifacts and inter-shot seams
entirely (see DECISIONS.md deviation #6).

Blocks sharing a group_id are hard-concatenated (continuity comes from
shared prompt/character-reference conditioning built once in
MschA2V_ShotPlanner, not per-block image-to-image chaining -- see
DECISIONS.md deviation #4); shot boundaries (a new shot's head block) get an
alpha-blend crossfade dissolve over `crossfade_frames`, read from the
incoming (later) block.
"""

from __future__ import annotations


class MschA2V_ShotAssembler:
    CATEGORY = "MschA2V"
    FUNCTION = "assemble"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latents": ("MSCHA2V_LATENTS",),
                "vae": ("VAE",),
            },
        }

    def assemble(self, latents, vae):
        import torch

        from ..h3 import adapter as h3adapter

        assembled = None

        for entry in latents["blocks"]:
            frames = h3adapter.decode_video_only(entry["av_latent"], vae)
            tp = entry["timing_plan"]
            fps = entry["fps"]
            block_len_frames = entry["block_len_frames"]

            trimmed_frames, _trimmed_audio, _report = h3adapter.trim_shot_output(
                frames,
                tp.main_prompt_start_seconds,
                block_len_frames / fps,
                audio=None,
                fps=fps,
            )
            # trim_shot_output re-derives its frame count from a
            # seconds-based round-trip (round((block_len_frames / fps) *
            # fps)), which can drift by a frame from floating-point error --
            # block_len_frames is already an exact integer, so enforce it
            # directly rather than trusting the round-trip.
            trimmed_frames = self._enforce_length(trimmed_frames, block_len_frames)
            trimmed_frames = self._apply_fades(trimmed_frames, entry["fade_in_frames"], entry["fade_out_frames"])

            if assembled is None:
                assembled = trimmed_frames
                continue

            if entry["group_id"] is not None and not entry["is_group_head"]:
                assembled = torch.cat([assembled, trimmed_frames], dim=0)
            else:
                crossfade = min(int(entry["crossfade_frames"]), assembled.shape[0], trimmed_frames.shape[0])
                assembled = self._crossfade_concat(assembled, trimmed_frames, crossfade)

        if assembled is None:
            assembled = torch.zeros((0, 8, 8, 3))

        if assembled.shape[0] != latents["total_frames"]:
            raise ValueError(
                f"MschA2V_ShotAssembler: assembled {assembled.shape[0]} frames but "
                f"latents['total_frames'] is {latents['total_frames']}. This usually means "
                "width/height/fps changed between planning and assembly, or the schedule_json "
                "was hand-edited after the shot plan was compiled."
            )

        return (assembled,)

    @staticmethod
    def _enforce_length(frames, target_len: int):
        import torch

        n = frames.shape[0]
        if n == target_len:
            return frames
        if n > target_len:
            return frames[:target_len]
        pad = frames[-1:].repeat(target_len - n, 1, 1, 1)
        return torch.cat([frames, pad], dim=0)

    @staticmethod
    def _apply_fades(frames, fade_in_frames: int, fade_out_frames: int):
        import torch

        n = frames.shape[0]
        if fade_in_frames <= 0 and fade_out_frames <= 0:
            return frames
        frames = frames.clone()
        if fade_in_frames > 0:
            k = min(int(fade_in_frames), n)
            ramp = torch.linspace(0.0, 1.0, k, device=frames.device, dtype=frames.dtype)
            frames[:k] = frames[:k] * ramp.view(k, 1, 1, 1)
        if fade_out_frames > 0:
            k = min(int(fade_out_frames), n)
            ramp = torch.linspace(1.0, 0.0, k, device=frames.device, dtype=frames.dtype)
            frames[n - k :] = frames[n - k :] * ramp.view(k, 1, 1, 1)
        return frames

    @staticmethod
    def _crossfade_concat(a, b, crossfade: int):
        import torch

        if crossfade <= 0:
            return torch.cat([a, b], dim=0)
        a_head, a_tail = a[:-crossfade], a[-crossfade:]
        b_fade, b_rest = b[:crossfade], b[crossfade:]
        alpha = torch.linspace(0.0, 1.0, crossfade, device=a.device, dtype=a.dtype).view(crossfade, 1, 1, 1)
        blended = a_tail * (1.0 - alpha) + b_fade * alpha
        return torch.cat([a_head, blended, b_rest], dim=0)


NODE_CLASS_MAPPINGS = {"MschA2V_ShotAssembler": MschA2V_ShotAssembler}
NODE_DISPLAY_NAME_MAPPINGS = {"MschA2V_ShotAssembler": "MschA2V Shot Assembler"}
