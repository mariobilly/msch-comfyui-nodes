"""MschA2V_LoadAudioPath, MschA2V_PreviewAudio: small standalone audio
utility nodes, useful for swapping the audio track post-hoc while keeping
the same Schedule, or previewing an AUDIO output without a full Save Video.
"""

from __future__ import annotations

import os
import uuid

from ._common import load_audio_dict


class MschA2V_LoadAudioPath:
    """Loads an arbitrary audio file path (not restricted to ComfyUI's input/
    directory) into an AUDIO output, with optional gain trim.
    """

    CATEGORY = "MschA2V"
    FUNCTION = "run"
    RETURN_TYPES = ("AUDIO", "FLOAT")
    RETURN_NAMES = ("audio", "duration_seconds")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"audio_path": ("STRING", {"default": ""})},
            "optional": {"gain_db": ("FLOAT", {"default": 0.0, "min": -60.0, "max": 24.0, "step": 0.1})},
        }

    def run(self, audio_path: str, gain_db: float = 0.0):
        audio = load_audio_dict(audio_path)
        if gain_db:
            gain = 10.0 ** (gain_db / 20.0)
            audio = {"waveform": audio["waveform"] * gain, "sample_rate": audio["sample_rate"]}
        duration = audio["waveform"].shape[-1] / float(audio["sample_rate"])
        return (audio, duration)


class MschA2V_PreviewAudio:
    """Writes a temp preview file and returns the standard ComfyUI
    audio-preview UI payload, so an AUDIO value can be auditioned in the
    graph without a full Save/Video Combine node.
    """

    CATEGORY = "MschA2V"
    FUNCTION = "run"
    RETURN_TYPES = ()
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"audio": ("AUDIO",)}}

    def run(self, audio):
        import folder_paths
        import soundfile as sf

        waveform = audio["waveform"][0].detach().cpu().numpy().T  # [samples, channels]
        sample_rate = int(audio["sample_rate"])

        temp_dir = folder_paths.get_temp_directory()
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"mscha2v_preview_{uuid.uuid4().hex[:8]}.flac"
        sf.write(os.path.join(temp_dir, filename), waveform, sample_rate, format="FLAC")

        return {"ui": {"audio": [{"filename": filename, "subfolder": "", "type": "temp"}]}}


NODE_CLASS_MAPPINGS = {
    "MschA2V_LoadAudioPath": MschA2V_LoadAudioPath,
    "MschA2V_PreviewAudio": MschA2V_PreviewAudio,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MschA2V_LoadAudioPath": "MschA2V Load Audio Path",
    "MschA2V_PreviewAudio": "MschA2V Preview Audio",
}
