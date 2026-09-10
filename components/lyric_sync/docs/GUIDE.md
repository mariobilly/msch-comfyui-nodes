> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# ComfyUI Lyric Sync

Load a video + a song, paste the lyrics, and rebuild the video as a **grid of
colored tiles filled with the song's lyric words** — the subject (dancer/person)
emerges out of the word-tiles, kinetic-typography style. Words follow the current
lyric line (synced to the music). Bilingual Arabic RTL + translation supported.

Three nodes:

| Node | In | Out |
|------|----|-----|
| **🎤 Lyric Sync — Align** | `AUDIO` (the song) + pasted `lyrics` (+ optional `translation`) | `LYRIC_TIMING` |
| **🟪 Lyric Sync — Word Mosaic** | `IMAGE` (frames) + `LYRIC_TIMING` + `frame_rate` + style | `IMAGE` |
| 🎤 Lyric Sync — Caption Overlay | `IMAGE` + `LYRIC_TIMING` + style | `IMAGE` (simple subtitle-box alt) |

### Word Mosaic — the main effect
Each frame is split into a grid of `cols` × rows tiles. Background tiles get a
vibrant palette colour + an Arabic lyric word; the video subject (dark pixels)
becomes grayscale tiles so the figure reads through the words. `auto_handle`
applies per-frame contrast + Otsu thresholding so **any** clip's subject separates
without a green screen. Key knobs: `cols` (grid density), `font_scale`, `gap`
(grid lines), `palette`, `sync_words`, `threshold_bias`/`invert_subject`,
`subject_min`/`subject_max` (figure shading).

## How sync works
Whisper mishears sung vocals, so **Align** uses WhisperX only to build a reliable
*word timeline* from the song, then snaps your **pasted** lyrics (the correct words)
onto that timeline. Words the transcription missed are filled by interpolation. If
WhisperX is unavailable, lines are distributed evenly across the song so nothing
hard-fails.

WhisperX is called via its **CLI** (it lives in a separate Python env on this
machine). Auto-detected via the host PATH / a known installation path. The legacy
`whisperx_exe` value is ignored; workflows cannot select an executable.

## Install
```
"...\python_embeded\python.exe" -m pip install arabic-reshaper python-bidi
```
Restart ComfyUI. The nodes appear under the **LyricSync** category.

## Example graph
```
VHS_LoadVideo ─► IMAGE ───────────────────────────────────┐
              └► VHS_VideoInfo ─► frame_rate ──────────────┤
VHS_LoadAudio (song) ─► AUDIO ─► [Lyric Sync — Align] ─► LYRIC_TIMING ─┐
                          lyrics / translation widgets                 │
                                                                       ▼
                       IMAGE + LYRIC_TIMING + frame_rate ─► [Lyric Sync — Overlay] ─► IMAGE
                                                                       │
                            IMAGE + song AUDIO + frame_rate ─► VHS_VideoCombine ─► .mp4
```
The **song** is the audio you wire into `VHS_VideoCombine`, so lyrics stay in sync
with the music in the final file.

## Style knobs (Overlay)
`bilingual`, `position` (bottom/center/top), `font_path`, `font_size` (0 = auto),
`text_color`, `box_color`, `box_opacity`, `corner_radius`, `padding`, `y_offset`,
`max_width_pct`, `fade_ms`, `hold_ms`, `highlight_words` + `highlight_color`.

Tweaking style re-runs only **Overlay** (fast); **Align** stays cached.

## Notes
- For Arabic, use a font with Arabic glyphs (`segoeui.ttf`, `tahoma.ttf`).
- First WhisperX run downloads its alignment model (one-time delay).
- Dense mixes align better if you isolate vocals first (e.g. the installed
  `ComfyUI-UVR5`) before feeding `AUDIO` into Align.
