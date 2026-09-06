"""
ComfyUI Lyric Sync
==================
Two nodes that turn a song + pasted lyrics into synced, boxed on-screen lyrics:

  LyricSyncAlign   : AUDIO + lyrics text  -> LYRIC_TIMING  (WhisperX forced-sync)
  LyricSyncOverlay : IMAGE + LYRIC_TIMING -> IMAGE         (PIL boxes, RTL, fade)

Designed to sit inside a VideoHelperSuite graph:
  VHS_LoadVideo --(IMAGE, frame_rate)-->                         \
  VHS_LoadAudio (song) --(AUDIO)--> LyricSyncAlign --(LYRIC_TIMING)--> LyricSyncOverlay --> VHS_VideoCombine
"""

from .align_node import LyricSyncAlign
from .overlay_node import LyricSyncOverlay
from .mosaic_node import LyricSyncMosaic
from .palette_node import LyricSyncPalette

NODE_CLASS_MAPPINGS = {
    "LyricSyncAlign": LyricSyncAlign,
    "LyricSyncPalette": LyricSyncPalette,
    "LyricSyncMosaic": LyricSyncMosaic,
    "LyricSyncOverlay": LyricSyncOverlay,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LyricSyncAlign": "🎤 Lyric Sync — Align",
    "LyricSyncPalette": "🎨 Lyric Sync — Palette",
    "LyricSyncMosaic": "🟪 Lyric Sync — Word Mosaic",
    "LyricSyncOverlay": "🎤 Lyric Sync — Caption Overlay",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("[LyricSync] loaded 4 nodes (Align, Palette, Word Mosaic, Caption Overlay).")
