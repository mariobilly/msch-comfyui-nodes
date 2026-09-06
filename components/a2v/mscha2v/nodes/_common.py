"""Small shared helpers used by more than one MschA2V node. Requires ComfyUI
(imports `folder_paths`, `comfy_extras`) -- never imported from mscha2v/core.
"""

from __future__ import annotations

import os


def resolve_audio_path(path: str) -> str:
    """Resolve a user-given audio path: absolute paths are used as-is if they
    exist; otherwise the path is tried relative to ComfyUI's input directory,
    then relative to the current working directory.
    """
    if not path:
        raise ValueError("audio_path is empty")
    if os.path.isabs(path) and os.path.isfile(path):
        return path

    import folder_paths

    input_dir = folder_paths.get_input_directory()
    candidate = os.path.join(input_dir, path)
    if os.path.isfile(candidate):
        return candidate
    if os.path.isfile(path):
        return os.path.abspath(path)

    raise FileNotFoundError(
        f"MschA2V: audio file not found: {path!r} (checked as an absolute path, "
        f"under ComfyUI's input directory {input_dir!r}, and relative to the working directory)"
    )


def load_audio_dict(path: str) -> dict:
    """Load an arbitrary audio file path into ComfyUI's standard AUDIO dict
    {"waveform": Tensor[B,C,S], "sample_rate": int}, reusing ComfyUI's own
    decoder (comfy_extras.nodes_audio.load) instead of reimplementing format
    handling. Not restricted to ComfyUI's managed input/ directory, unlike
    the built-in LoadAudio node.
    """
    from comfy_extras import nodes_audio

    resolved = resolve_audio_path(path)
    waveform, sample_rate = nodes_audio.load(resolved)
    return {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}
