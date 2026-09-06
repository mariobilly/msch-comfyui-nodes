"""Adapter over the installed MiniMax H3 ComfyUI pack (comfyui-minimax-h3-audio-T8).

This is the ONE place mscha2v talks to that pack's internals. Every function
below is a thin, documented wrapper around a real H3 pack function -- nothing
here reimplements H3's timing/conditioning/sampling/decode logic. See
DECISIONS.md "H3 Introspection" for exact source citations.

Everything here is lazy: comfy/torch and the H3 pack itself are only
imported the first time one of these functions actually runs, never at
module import time. That keeps `mscha2v.nodes.*` importable during ComfyUI's
node-registration scan even if the H3 pack briefly isn't ready yet, and keeps
`mscha2v.core`/`mscha2v.h3` importable under plain pytest with no ComfyUI/H3
pack installed at all (nothing in mscha2v/core imports this module).
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path

_KNOWN_PACK_DIR_NAMES = ("comfyui-minimax-h3-audio-T8",)
_SYNTHETIC_PACKAGE_NAME = "_mscha2v_h3_pack"

_h3_modules: types.SimpleNamespace | None = None


class H3PackNotFoundError(RuntimeError):
    """Raised when the installed MiniMax H3 ComfyUI pack cannot be located."""


def _candidate_custom_node_roots() -> list[Path]:
    """Directories to search for the installed H3 pack, in priority order."""
    roots: list[Path] = []
    try:
        import folder_paths  # type: ignore

        for p in folder_paths.get_folder_paths("custom_nodes"):
            roots.append(Path(p))
    except Exception:
        pass
    # mscha2v lives at <custom_nodes>/ComfyUI-MschA2V/mscha2v/h3/adapter.py,
    # so parents[3] of this file is <custom_nodes> -- a reliable fallback
    # even if folder_paths isn't importable (e.g. this pack was symlinked
    # somewhere folder_paths doesn't report).
    roots.append(Path(__file__).resolve().parents[3])
    seen: set[Path] = set()
    unique: list[Path] = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


def _locate_h3_pack_dir() -> Path:
    override = os.environ.get("MSCHA2V_H3_PACK_DIR")
    if override:
        p = Path(override)
        if (p / "core.py").exists():
            return p
        raise H3PackNotFoundError(f"MSCHA2V_H3_PACK_DIR={override!r} does not contain core.py")

    for root in _candidate_custom_node_roots():
        if not root.is_dir():
            continue
        for name in _KNOWN_PACK_DIR_NAMES:
            candidate = root / name
            if (candidate / "core.py").exists() and (candidate / "timing.py").exists():
                return candidate
        for candidate in sorted(root.glob("*minimax*h3*")):
            if candidate.is_dir() and (candidate / "core.py").exists():
                return candidate

    raise H3PackNotFoundError(
        "MschA2V: could not find the installed MiniMax H3 ComfyUI pack "
        f"(looked for {_KNOWN_PACK_DIR_NAMES!r} and '*minimax*h3*' under each custom_nodes root). "
        "Install comfyui-minimax-h3-audio-T8, or set the MSCHA2V_H3_PACK_DIR environment "
        "variable to point at its directory."
    )


def _load_h3_modules() -> types.SimpleNamespace:
    """Load (and memoize) the H3 pack's submodules via a synthetic package.

    The pack's own directory name is hyphenated, so it can't be `import`ed by
    dotted path. This mirrors the pack's own fallback trick in its
    `__init__.py` (used there for standalone test collection): register a
    bare `types.ModuleType` in sys.modules with `__path__` pointed at the
    pack's real directory, which makes it a valid (if synthetic) Python
    package. Once that's registered, `importlib.import_module` on its
    submodules works exactly like a normal package import -- including the
    submodules' own internal relative imports (e.g. timing.py's
    `from .core import FPS, ...`), since those resolve through the same
    registered package.
    """
    global _h3_modules
    if _h3_modules is not None:
        return _h3_modules

    pack_dir = _locate_h3_pack_dir()

    if _SYNTHETIC_PACKAGE_NAME not in sys.modules:
        package = types.ModuleType(_SYNTHETIC_PACKAGE_NAME)
        package.__path__ = [str(pack_dir)]
        sys.modules[_SYNTHETIC_PACKAGE_NAME] = package

    def _sub(name: str):
        return importlib.import_module(f"{_SYNTHETIC_PACKAGE_NAME}.{name}")

    _h3_modules = types.SimpleNamespace(
        core=_sub("core"),
        timing=_sub("timing"),
        conditioning=_sub("conditioning"),
        audio_ops=_sub("audio_ops"),
        sampling=_sub("sampling"),
        preflight=_sub("preflight"),
        prompt_tags=_sub("prompt_tags"),
    )
    return _h3_modules


# ---------------------------------------------------------------------------
# Frame grid / bucket solving (core.py)
# ---------------------------------------------------------------------------


def align_frame_count(n: int) -> int:
    """-> h3 pack core.align_frame_count(n). The live, authoritative grid rule."""
    return _load_h3_modules().core.align_frame_count(n)


def solve_bucket_via_h3(n_frames: int) -> tuple[int, int]:
    """Authoritative cross-check for mscha2v.core.buckets.solve_bucket:
    recomputes (bucket_frames, trim_tail) directly from the live H3 pack's
    align_frame_count/MIN_TRAINED_FRAMES/MAX_TRAINED_FRAMES, instead of the
    mirrored copy in mscha2v/core/buckets.py.
    """
    h3core = _load_h3_modules().core
    bucket_frames = max(h3core.align_frame_count(n_frames), h3core.MIN_TRAINED_FRAMES)
    if bucket_frames > h3core.MAX_TRAINED_FRAMES:
        raise ValueError(
            f"{n_frames} frames aligns to {bucket_frames}, which exceeds the installed H3 "
            f"pack's MAX_TRAINED_FRAMES={h3core.MAX_TRAINED_FRAMES}. Split this block/shot."
        )
    return bucket_frames, bucket_frames - n_frames


def constants() -> dict:
    """Live FPS/AUDIO_LATENT_FPS/MIN_TRAINED_FRAMES/MAX_TRAINED_FRAMES from the installed pack."""
    h3core = _load_h3_modules().core
    return {
        "FPS": h3core.FPS,
        "AUDIO_LATENT_FPS": h3core.AUDIO_LATENT_FPS,
        "MIN_TRAINED_FRAMES": h3core.MIN_TRAINED_FRAMES,
        "MAX_TRAINED_FRAMES": h3core.MAX_TRAINED_FRAMES,
    }


# ---------------------------------------------------------------------------
# Timing / audio windowing (timing.py)
# ---------------------------------------------------------------------------


def plan_shot_timing(
    scene_start_seconds: float,
    scene_duration_seconds: float,
    warmup_seconds: float = 0.0,
    cooldown_seconds: float = 0.0,
    ensure_minimum_context: bool = True,
    source_duration_seconds: float = 0.0,
):
    """-> h3 pack timing.make_timing_plan(...) -> TimingPlan."""
    h3 = _load_h3_modules()
    return h3.timing.make_timing_plan(
        scene_start_seconds,
        scene_duration_seconds,
        warmup_seconds,
        cooldown_seconds,
        ensure_minimum_context,
        source_duration_seconds,
    )


def window_audio(audio: dict, plan):
    """-> h3 pack timing.window_audio(audio, plan)."""
    return _load_h3_modules().timing.window_audio(audio, plan)


# ---------------------------------------------------------------------------
# Conditioning (conditioning.py) -- builds the positive conditioning AND the
# initial (possibly audio-locked) empty AV latent in one call.
# ---------------------------------------------------------------------------


def build_conditioning(
    clip,
    video_vae,
    audio_vae,
    prompt: str,
    width: int,
    height: int,
    length: int,
    task_type: str = "auto",
    audio_mode: str = "lock_source",
    audio_denoise_strength: float = 0.35,
    add_source_as_reference: bool = True,
    drive_audio=None,
    first_frame=None,
    last_frame=None,
    **kwargs,
):
    """-> h3 pack conditioning.build_conditioning(...) ->
    (conditioning, av_latent, output_audio, conditioned_prompt, media_map, report_text).

    Returns POSITIVE conditioning only -- callers needing negative
    conditioning must build it separately with a plain CLIP text-encode.
    """
    h3 = _load_h3_modules()
    return h3.conditioning.build_conditioning(
        clip,
        video_vae,
        audio_vae,
        prompt,
        width,
        height,
        length,
        task_type=task_type,
        audio_mode=audio_mode,
        audio_denoise_strength=audio_denoise_strength,
        add_source_as_reference=add_source_as_reference,
        drive_audio=drive_audio,
        first_frame=first_frame,
        last_frame=last_frame,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Sampling (sampling.py)
# ---------------------------------------------------------------------------


def setup_dual_clock_sampling(
    model,
    av_latent,
    steps: int,
    shift_video: float,
    shift_audio: float,
    sampler_name: str | None = None,
    scheduler: str | None = None,
):
    """-> h3 pack sampling.setup_dual_clock_sampling(...) -> (patched_model, sampler, sigmas).

    This is a SAMPLER/SIGMAS *setup* function, not a full KSampler -- it
    takes no cfg/positive/negative/seed. Callers build noise + a CFGGuider
    themselves (the same pattern ComfyUI's native SamplerCustomAdvanced uses)
    and call `guider.sample(noise, latent, sampler, sigmas, seed=...)`.
    """
    h3 = _load_h3_modules()
    if sampler_name is None:
        sampler_name = h3.sampling.DEFAULT_SAMPLER_NAME
    if scheduler is None:
        scheduler = h3.sampling.DEFAULT_SCHEDULER_NAME
    return h3.sampling.setup_dual_clock_sampling(model, av_latent, steps, shift_video, shift_audio, sampler_name, scheduler)


def sampler_options() -> list[str]:
    return list(_load_h3_modules().sampling.SAMPLER_OPTIONS)


def scheduler_options() -> list[str]:
    return list(_load_h3_modules().sampling.SCHEDULER_OPTIONS)


def default_sampler_name() -> str:
    return _load_h3_modules().sampling.DEFAULT_SAMPLER_NAME


def default_scheduler_name() -> str:
    return _load_h3_modules().sampling.DEFAULT_SCHEDULER_NAME


# ---------------------------------------------------------------------------
# Decode / trim (audio_ops.py)
# ---------------------------------------------------------------------------


def decode_shot(av_latent, video_vae, audio_vae):
    """-> h3 pack audio_ops.decode_av_latent(...) -> (frames, generated_audio, video_latent, audio_latent)."""
    return _load_h3_modules().audio_ops.decode_av_latent(av_latent, video_vae, audio_vae)


def decode_video_only(av_latent, video_vae):
    """Decode just the video branch of an AV latent -- no audio_vae needed.

    Mirrors audio_ops.py's decode_av_latent verbatim for the video half only
    (`video, audio = nested_av_parts(av_latent); images = video_vae.decode(video);
    if images.ndim == 5: images = images.reshape(-1, *images.shape[-3:])`),
    confirmed by reading audio_ops.py:25-29 directly. Used by
    MschA2V_ShotAssembler and MschA2V_BeatPixelUpscaleKSampler, which take a
    single `vae` (video) input and never touch the audio branch at all --
    the original song audio is always used for the final output instead
    (see DECISIONS.md deviation #6).
    """
    video, _audio = av_latent["samples"].unbind()
    images = video_vae.decode(video)
    if images.ndim == 5:
        images = images.reshape(-1, *images.shape[-3:])
    return images


def trim_shot_output(frames, start_seconds: float, duration_seconds: float, audio=None, fps: float = 24.0):
    """-> h3 pack audio_ops.trim_av_output(...) -> (frames, audio, report)."""
    return _load_h3_modules().audio_ops.trim_av_output(frames, start_seconds, duration_seconds, audio=audio, fps=fps)


# ---------------------------------------------------------------------------
# Validation (preflight.py, prompt_tags.py)
# ---------------------------------------------------------------------------


def run_preflight(width, height, length, audio_mode, **kwargs):
    """-> h3 pack preflight.run_preflight(...) -> (ready, warning_count, report_json)."""
    return _load_h3_modules().preflight.run_preflight(width, height, length, audio_mode, **kwargs)


def prepare_prompt(prompt: str, counts, source_audio_ordinal: int = 0, prompt_primary_audio_ordinal: int = 1, strict: bool = True):
    """-> h3 pack prompt_tags.prepare_prompt(...). Canonicalizes optional
    <Picture/Video/Audio N> reference tags; raises ValueError on an
    out-of-range ordinal when strict=True. Only ever called at render time
    (inside build_conditioning), never at MschA2V's planning layer, so
    mscha2v.core.schedule keeps prompt text fully byte-for-byte/unvalidated.
    """
    return _load_h3_modules().prompt_tags.prepare_prompt(
        prompt,
        counts,
        source_audio_ordinal=source_audio_ordinal,
        prompt_primary_audio_ordinal=prompt_primary_audio_ordinal,
        strict=strict,
    )
