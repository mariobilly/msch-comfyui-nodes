"""LyricSyncAlign node — song audio + pasted lyrics -> timed LYRIC_TIMING."""

import json

from .aligner import align_lyrics


class LyricSyncAlign:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "lyrics": ("STRING", {
                    "multiline": True,
                    "default": "Paste the song lyrics here.\nOne line per on-screen box.",
                }),
            },
            "optional": {
                "translation": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Optional parallel translation, one line per lyric line.",
                }),
                "language": ("STRING", {"default": "auto"}),
                "whisper_model": (
                    ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                    {"default": "medium"},
                ),
                "whisperx_exe": ("STRING", {
                    "default": "",
                    "tooltip": "Optional path to whisperx.exe (auto-detected if blank).",
                }),
            },
        }

    RETURN_TYPES = ("LYRIC_TIMING", "STRING")
    RETURN_NAMES = ("timing", "timing_json")
    FUNCTION = "align"
    CATEGORY = "LyricSync"

    def align(self, audio, lyrics, translation="", language="auto",
              whisper_model="medium", whisperx_exe=""):
        timing = align_lyrics(
            audio=audio,
            lyrics=lyrics,
            translation=translation,
            language=language,
            model=whisper_model,
            whisperx_exe=whisperx_exe,
        )
        timing_json = json.dumps(timing, ensure_ascii=False, indent=2)
        return (timing, timing_json)
