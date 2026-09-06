"""MschA2V_BeatKSampler: samples each block's pre-built conditioning+latent
(from MschA2V_ShotPlanner) through the installed MiniMax H3 model.

Deliberately minimal inputs (model + shot_plan + standard sampler params) --
all clip/vae/audio-conditioning work already happened in
MschA2V_ShotPlanner, matching the reference MiniMax H3 beat-sync workflow
topology (see DECISIONS.md deviation #3, revised). Progress is reported per
block via comfy.utils.ProgressBar since nothing in the H3 pack wraps an
outer per-block bar itself.

Output is MSCHA2V_LATENTS, not MSCHA2V_SHOT_PLAN -- a deliberately leaner
type carrying the sampled av_latent + per-block timing/fade/crossfade/group
metadata but NOT positive/negative conditioning (nothing downstream of this
node needs to re-run conditioning against the original shot_plan except
MschA2V_BeatPixelUpscaleKSampler, which takes the original MSCHA2V_SHOT_PLAN
back in as a *separate* input for exactly that reason -- see DECISIONS.md
deviation #3).
"""

from __future__ import annotations


def _fallback_sampler_options():
    return ["dual_clock_euler"], ["native_flow"], "dual_clock_euler", "native_flow"


class MschA2V_BeatKSampler:
    CATEGORY = "MschA2V"
    FUNCTION = "sample"
    RETURN_TYPES = ("MSCHA2V_LATENTS",)
    RETURN_NAMES = ("latents",)

    @classmethod
    def INPUT_TYPES(cls):
        try:
            from ..h3 import adapter as h3adapter

            sampler_options = h3adapter.sampler_options()
            scheduler_options = h3adapter.scheduler_options()
            default_sampler = h3adapter.default_sampler_name()
            default_scheduler = h3adapter.default_scheduler_name()
        except Exception:
            sampler_options, scheduler_options, default_sampler, default_scheduler = _fallback_sampler_options()

        return {
            "required": {
                "model": ("MODEL",),
                "shot_plan": ("MSCHA2V_SHOT_PLAN",),
                "steps": ("INT", {"default": 4, "min": 1, "max": 1000}),
                "shift_video": ("FLOAT", {"default": 12.0, "min": 0.01, "max": 100.0, "step": 0.01}),
                "shift_audio": ("FLOAT", {"default": 3.0, "min": 0.01, "max": 100.0, "step": 0.01}),
                "sampler_name": (sampler_options, {"default": default_sampler}),
                "scheduler": (scheduler_options, {"default": default_scheduler}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                # Standard ComfyUI seed convention (the frontend adds the
                # increment/randomize/fixed control automatically for any
                # INT widget named "seed"). A block's own explicit seed
                # override (set in the Sequencer's Inspector) always wins;
                # otherwise each block gets `seed + its running index`.
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
            },
        }

    def sample(self, model, shot_plan, steps, shift_video, shift_audio, sampler_name, scheduler, cfg, denoise, seed):
        import comfy.sample
        import comfy.samplers
        import comfy.utils

        from ..h3 import adapter as h3adapter

        blocks = shot_plan["blocks"]
        pbar = comfy.utils.ProgressBar(max(len(blocks), 1))

        sampled_blocks = []
        for i, block in enumerate(blocks):
            resolved_seed = block["seed_override"] if block["seed_override"] is not None else (seed + i) & 0xFFFFFFFF

            patched_model, sampler, sigmas = h3adapter.setup_dual_clock_sampling(
                model, block["av_latent"], steps, shift_video, shift_audio, sampler_name, scheduler
            )
            start_step = steps - round(steps * denoise)
            sigmas = sigmas[start_step:]

            latent_tensor = block["av_latent"]["samples"]
            noise = comfy.sample.prepare_noise(latent_tensor, resolved_seed)

            guider = comfy.samplers.CFGGuider(patched_model)
            guider.set_conds(block["positive"], block["negative"])
            guider.set_cfg(cfg)

            # Preserve the audio-branch noise_mask (e.g. lock_source's
            # all-zero freeze) all the way through sampling -- without this,
            # "lock_source" would only affect the *initial* latent, not what
            # the sampler actually denoises.
            noise_mask = block["av_latent"].get("noise_mask")
            sampled = guider.sample(noise, latent_tensor, sampler, sigmas, denoise_mask=noise_mask, seed=resolved_seed)

            result_av_latent = dict(block["av_latent"])
            result_av_latent["samples"] = sampled
            result_av_latent.pop("noise_mask", None)

            sampled_blocks.append(
                {
                    "block_id": block["block_id"],
                    "group_id": block["group_id"],
                    "is_group_head": block["is_group_head"],
                    "is_group_tail": block["is_group_tail"],
                    "av_latent": result_av_latent,
                    "seed": resolved_seed,
                    "timing_plan": block["timing_plan"],
                    "block_len_frames": block["block_len_frames"],
                    "fps": block["fps"],
                    "fade_in_frames": block["fade_in_frames"],
                    "fade_out_frames": block["fade_out_frames"],
                    "crossfade_frames": block["crossfade_frames"],
                }
            )
            pbar.update(1)

        latents = {
            "fps": shot_plan["fps"],
            "total_frames": shot_plan["total_frames"],
            "audio_path": shot_plan["audio_path"],
            "blocks": sampled_blocks,
        }
        return (latents,)


NODE_CLASS_MAPPINGS = {"MschA2V_BeatKSampler": MschA2V_BeatKSampler}
NODE_DISPLAY_NAME_MAPPINGS = {"MschA2V_BeatKSampler": "MschA2V Beat KSampler"}
