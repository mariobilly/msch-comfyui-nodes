"""Small shared helpers used by more than one MschA2V node. Requires ComfyUI
(imports `folder_paths`, `comfy_extras`) -- never imported from mscha2v/core.
"""

from __future__ import annotations

from ...._paths import input_path


def resolve_audio_path(path: str) -> str:
    """Resolve an audio file strictly underneath ComfyUI's input directory."""
    return str(input_path(path))


def load_audio_dict(path: str) -> dict:
    """Load an input-relative audio file into ComfyUI's standard AUDIO dict
    {"waveform": Tensor[B,C,S], "sample_rate": int}, reusing ComfyUI's own
    decoder (comfy_extras.nodes_audio.load) instead of reimplementing format
    handling. Paths are restricted to ComfyUI's managed input/ directory.
    """
    from comfy_extras import nodes_audio

    resolved = resolve_audio_path(path)
    waveform, sample_rate = nodes_audio.load(resolved)
    return {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}
