# MSCH Lyric Sync: node reference

Align pasted lyrics to audio and render bilingual captions or animated lyric mosaics with editable color palettes.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## LyricSyncAlign

**Display name:** 🎤 Lyric Sync — Align  
**Category:** `LyricSync`  
**Output node:** no

Combine a ComfyUI AUDIO value with user-supplied lyric lines. The optional WhisperX CLI supplies a word timeline that is matched to the pasted lyrics; unmatched words are interpolated. If that alignment cannot run, lines are spread evenly across the audio duration. Returns structured LYRIC_TIMING plus a readable JSON STRING. Optional translation lines support bilingual rendering.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `audio` | AUDIO | — |  |  |
| `lyrics` | STRING | Paste the song lyrics here.<br>One line per on-screen box. |  |  Multiline text is supported. |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `translation` | STRING |  |  | Optional parallel translation, one line per lyric line. Multiline text is supported. |
| `language` | STRING | auto |  |  |
| `whisper_model` | COMBO | medium | tiny, base, small, medium, large-v2, large-v3 |  |
| `whisperx_exe` | STRING |  |  | Optional path to whisperx.exe (auto-detected if blank). |

### Outputs

| Socket | Type |
|---|---|
| `timing` | `LYRIC_TIMING` |
| `timing_json` | `STRING` |

## LyricSyncPalette

**Display name:** 🎨 Lyric Sync — Palette  
**Category:** `LyricSync`  
**Output node:** no

Build a normalized palette from up to twelve color swatches plus additional newline-separated hex colors. num_colors controls how many slots participate, and weight_white adds repeated white entries to alter sampling frequency. Outputs a PALETTE list for Mosaic's palette_in and a comma-separated STRING for its palette text field.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `num_colors` | INT | 10 | 1 to 12 | How many of the swatches below to use. |
| `color_01` | STRING | #FFFFFF |  |  |
| `color_02` | STRING | #7DEFA1 |  |  |
| `color_03` | STRING | #5FE39A |  |  |
| `color_04` | STRING | #F25CC1 |  |  |
| `color_05` | STRING | #FF74B8 |  |  |
| `color_06` | STRING | #63D6F0 |  |  |
| `color_07` | STRING | #9B5DE5 |  |  |
| `color_08` | STRING | #B388F0 |  |  |
| `color_09` | STRING | #F5B8D6 |  |  |
| `color_10` | STRING | #FFFFFF |  |  |
| `color_11` | STRING | #15151E |  |  |
| `color_12` | STRING | #FFD23F |  |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `extra_hex` | STRING |  |  | More colours, one #hex per line (unlimited). Multiline text is supported. |
| `weight_white` | INT | 1 | 0 to 8 | Extra copies of white added — raises the share of white tiles. |

### Outputs

| Socket | Type |
|---|---|
| `palette` | `PALETTE` |
| `palette_csv` | `STRING` |

## LyricSyncMosaic

**Display name:** 🟪 Lyric Sync — Word Mosaic  
**Category:** `LyricSync`  
**Output node:** no

Rebuild video frames as a scrolling text grid with colored cells and lyric word boxes. LYRIC_TIMING selects active words at frame_index / frame_rate. Background keying and tonal controls reveal the original subject through the grid. Connect a Palette node to palette_in or enter comma-separated colors in palette. Returns an IMAGE batch; the original soundtrack is connected separately to the encoder.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `timing` | LYRIC_TIMING | — |  |  |
| `frame_rate` | FLOAT | 25.0 | 1.0 to 240.0; step 0.001 |  |
| `cols` | INT | 56 | 10 to 220 | Letter cells across the frame (higher = finer/denser). |
| `font_path` | STRING | C:\Windows\Fonts\tahoma.ttf |  |  |
| `letter_scale` | FLOAT | 0.72 | 0.3 to 1.0; step 0.02 |  |
| `scroll_dir` | COMBO | down | down, up, left, right, none |  |
| `scroll_speed` | FLOAT | 0.12 | 0.0 to 1.0; step 0.01 | Cells per frame the grid drifts. |
| `color_density` | FLOAT | 0.13 | 0.0 to 0.6; step 0.01 | Fraction of letter cells that light up with colour. |
| `flicker_period` | INT | 4 | 1 to 60 | Frames between colour-cell flicker changes (lower = faster). |
| `wordbox_density` | FLOAT | 0.6 | 0.0 to 1.0; step 0.05 | How many of the current line's word boxes show at once. |
| `wordbox_scale` | FLOAT | 2.3 | 1.0 to 5.0; step 0.1 | Word-box height relative to a letter cell. |
| `bg_key` | BOOLEAN | True |  | Key out the backdrop to find the subject (best for plain backgrounds). |
| `bg_tol` | FLOAT | 0.0 | 0.0 to 1.0; step 0.02 | 0 = auto. Lower keeps more of the frame as subject. |
| `threshold_bias` | FLOAT | 0.0 | -0.4 to 0.4; step 0.02 |  |
| `invert_subject` | BOOLEAN | False |  |  |
| `fg_detail` | FLOAT | 3.0 | 1.0 to 6.0; step 0.5 |  |
| `posterize` | INT | 7 | 2 to 32 |  |
| `subject_max` | FLOAT | 0.95 | 0.2 to 1.0; step 0.02 |  |
| `subject_gamma` | FLOAT | 0.6 | 0.3 to 3.0; step 0.05 | <1 brightens a dark subject; >1 darkens. |
| `fg_gap` | INT | 0 | 0 to 4 |  |
| `text_color` | STRING | #15151E |  |  |
| `seed` | INT | 7 | 0 to 99999 |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `palette_in` | PALETTE | — |  | Connect a 🎨 Lyric Sync — Palette node (overrides the text below). |
| `palette` | STRING | #FFFFFF,#FFFFFF,#7DEFA1,#5FE39A,#F25CC1,#FF74B8,#63D6F0,#9B5DE5,#B388F0,#F5B8D6 |  | Comma-separated hex colours (used if no Palette node connected). |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |

## LyricSyncOverlay

**Display name:** 🎤 Lyric Sync — Caption Overlay  
**Category:** `LyricSync`  
**Output node:** no

Draw timed lyric captions in rounded boxes over IMAGE frames. Position, font, width, padding and opacity define the layout; fade and hold settings shape transitions. Optional translation and right-to-left shaping support bilingual captions. Word highlighting follows supplied word timestamps, whose accuracy depends on the alignment method. Returns frames without attaching audio.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `timing` | LYRIC_TIMING | — |  |  |
| `frame_rate` | FLOAT | 30.0 | 1.0 to 240.0; step 0.001 |  |
| `bilingual` | BOOLEAN | True |  |  |
| `position` | COMBO | bottom | bottom, center, top |  |
| `font_path` | STRING | C:\Windows\Fonts\segoeui.ttf |  |  |
| `font_size` | INT | 0 | 0 to 400 | 0 = auto from frame width |
| `text_color` | STRING | #FFFFFF |  |  |
| `box_color` | STRING | #000000 |  |  |
| `box_opacity` | FLOAT | 0.6 | 0.0 to 1.0; step 0.05 |  |
| `corner_radius` | INT | 18 | 0 to 200 |  |
| `padding` | INT | 24 | 0 to 200 |  |
| `y_offset` | INT | 0 | -2000 to 2000 |  |
| `max_width_pct` | FLOAT | 0.8 | 0.2 to 1.0; step 0.05 |  |
| `fade_ms` | INT | 150 | 0 to 2000 |  |
| `hold_ms` | INT | 0 | 0 to 3000 | Keep each line on screen this long past its end. |
| `highlight_words` | BOOLEAN | False |  |  |
| `highlight_color` | STRING | #FFDC50 |  |  |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |
