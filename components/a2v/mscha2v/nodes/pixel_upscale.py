"""MschA2V_BeatPixelUpscaleKSampler: local second-pass pixel upscaler.

Lets a creator prototype timing at a small resolution (e.g. 288x512, cheap
and fast for a multi-minute timing pass) and then push the assembled render
up to 1024-1920px long side entirely locally, with the same per-block
conditioning and seeds -- no closed 2K refiner needed.

Takes the original MSCHA2V_SHOT_PLAN (for conditioning -- positive/negative
per block, built once by MschA2V_ShotPlanner) AND the current
MSCHA2V_LATENTS (for the actual sampled tensor to upscale from) as two
SEPARATE inputs, matched by block_id -- MSCHA2V_LATENTS deliberately doesn't
carry conditioning (see beat_ksampler.py), so re-sampling at a new
resolution needs both. Decodes each block's own latent (video branch only,
no audio_vae needed), pixel-upscales it, VAE-encodes it back into H3's
latent space, and partially re-samples using the SAME conditioning/seed as
the low-res pass. Outputs a new MSCHA2V_LATENTS at the higher resolution --
feed it into another MschA2V_ShotAssembler to get the final IMAGE.
"""

from __future__ import annotations


def _scale_to_long_side(height: int, width: int, target_long_side: int, multiple: int = 32) -> tuple[int, int]:
    long_side = max(height, width)
    scale = target_long_side / float(long_side)
    new_h = max(multiple, round(height * scale / multiple) * multiple)
    new_w = max(multiple, round(width * scale / multiple) * multiple)
    return new_h, new_w


def _fallback_sampler_options():
    return ["dual_clock_euler"], ["native_flow"], "dual_clock_euler", "native_flow"


class MschA2V_BeatPixelUpscaleKSampler:
    CATEGORY = "MschA2V"
    FUNCTION = "upscale"
    RETURN_TYPES = ("MSCHA2V_LATENTS",)
    RETURN_NAMES = ("latent",)

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
                "latent": ("MSCHA2V_LATENTS",),
                "vae": ("VAE",),
                "target_long_side": ("INT", {"default": 1024, "min": 512, "max": 1920, "step": 32}),
                "upscale_method": (["lanczos", "bicubic", "bilinear", "nearest-exact"], {"default": "lanczos"}),
                "steps": ("INT", {"default": 40, "min": 1, "max": 1000}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "denoise": ("FLOAT", {"default": 0.75, "min": 0.0, "max": 1.0, "step": 0.01}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
                "sampler_name": (sampler_options, {"default": default_sampler}),
                "scheduler": (scheduler_options, {"default": default_scheduler}),
            }
        }

    def upscale(
        self,
        model,
        shot_plan,
        latent,
        vae,
        target_long_side,
        upscale_method,
        steps,
        cfg,
        denoise,
        seed,
        sampler_name,
        scheduler,
    ):
        import comfy.nested_tensor
        import comfy.sample
        import comfy.samplers
        import comfy.utils

        from ..h3 import adapter as h3adapter

        conditioning_by_block = {b["block_id"]: b for b in shot_plan["blocks"]}

        blocks = latent["blocks"]
        pbar = comfy.utils.ProgressBar(max(len(blocks), 1))

        new_blocks = []
        for i, entry in enumerate(blocks):
            cond_block = conditioning_by_block.get(entry["block_id"])
            if cond_block is None:
                raise ValueError(
                    f"MschA2V_BeatPixelUpscaleKSampler: no matching block {entry['block_id']!r} in shot_plan "
                    "-- shot_plan and latent must come from the same MschA2V_ShotPlanner run."
                )

            # Decode+upscale the FULL padded render window (not just the
            # trimmed real-content span) so the frame count matches exactly
            # for the VAE re-encode below; MschA2V_ShotAssembler trims once,
            # downstream, using the same stored timing_plan either way.
            frames = h3adapter.decode_video_only(entry["av_latent"], vae)

            src_h, src_w = int(frames.shape[1]), int(frames.shape[2])
            new_h, new_w = _scale_to_long_side(src_h, src_w, target_long_side)

            pixels = frames[..., :3].movedim(-1, 1)
            pixels = comfy.utils.common_upscale(pixels, new_w, new_h, upscale_method, "disabled")
            pixels = pixels.movedim(1, -1)

            encoded = vae.encode(pixels)
            encoded_samples = encoded["samples"] if isinstance(encoded, dict) else encoded

            # av_latent["samples"] is always a NestedTensor((video, audio));
            # substitute our own upscaled+re-encoded pixels for the video
            # half only, keeping the (already audio-locked) audio half
            # exactly as it was in the low-res pass. entry["av_latent"] is
            # the low-res BeatKSampler's cached output, which by the time
            # this node runs may have been relocated to CPU by ComfyUI's
            # dynamic VRAM management (it can sit cached for a while behind
            # other VAE loads/unloads) -- realign it to encoded_samples'
            # device/dtype, the tensor we just freshly produced on whatever
            # device is actually active right now.
            _old_video, audio_template = entry["av_latent"]["samples"].unbind()
            audio_template = audio_template.to(device=encoded_samples.device, dtype=encoded_samples.dtype)
            new_av_latent = dict(entry["av_latent"])
            new_av_latent["samples"] = comfy.nested_tensor.NestedTensor((encoded_samples, audio_template))
            new_av_latent.pop("noise_mask", None)

            patched_model, sampler, sigmas = h3adapter.setup_dual_clock_sampling(
                model, new_av_latent, steps, 12.0, 3.0, sampler_name, scheduler
            )
            start_step = steps - round(steps * denoise)
            sigmas = sigmas[start_step:]

            # Reuse the EXACT seed the low-res pass used for this block
            # (stored by MschA2V_BeatKSampler) for a fully reproducible,
            # deterministic upscale rather than a fresh one.
            resolved_seed = entry.get("seed")
            if resolved_seed is None:
                resolved_seed = (seed + i) & 0xFFFFFFFF

            latent_tensor = new_av_latent["samples"]
            noise = comfy.sample.prepare_noise(latent_tensor, resolved_seed)

            guider = comfy.samplers.CFGGuider(patched_model)
            guider.set_conds(cond_block["positive"], cond_block["negative"])
            guider.set_cfg(cfg)
            sampled = guider.sample(noise, latent_tensor, sampler, sigmas, seed=resolved_seed)

            result_av_latent = dict(new_av_latent)
            result_av_latent["samples"] = sampled

            new_blocks.append({**entry, "av_latent": result_av_latent, "seed": resolved_seed})
            pbar.update(1)

        return ({**latent, "blocks": new_blocks},)


NODE_CLASS_MAPPINGS = {"MschA2V_BeatPixelUpscaleKSampler": MschA2V_BeatPixelUpscaleKSampler}
NODE_DISPLAY_NAME_MAPPINGS = {"MschA2V_BeatPixelUpscaleKSampler": "MschA2V Beat Pixel Upscale KSampler"}
