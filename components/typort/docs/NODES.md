# MSCH Typort: node reference

Layered animated typography studio with Arabic text, keyframes, audio reactions and transparent or composite exports.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## MarioTyport

**Display name:** mariotyport  
**Category:** `mariotyport`  
**Output node:** yes

Author layered motion typography in the browser studio and export it through the same canvas renderer. The saved project contains text layers, styles, timing, easing, keyframes and optional audio analysis. Node settings set output resolution, FPS and format. Transparent MOV/PNG outputs preserve alpha; MP4 composites include a background and optional footage. Returns export path, poster IMAGE, alpha MASK and editable project JSON.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `text` | STRING | MAKE<br>IT MATTER |  |  Multiline text is supported. |
| `font` | COMBO | Black | Black, ExtraBold, Bold, Medium, Regular, Light, ExtraLight |  |
| `animation` | COMBO | Line reveal | Line reveal, Word cascade, Scale impact, Editorial drift, Side sweep, Tracking reveal, Rise, Fade, Static |  |
| `duration` | FLOAT | 5 | 0.1 to 600; step 0.1 |  |
| `width` | INT | 1920 | 64 to 4096; step 2 |  |
| `height` | INT | 1080 | 64 to 4096; step 2 |  |
| `fps` | INT | 30 | 1 to 60 |  |
| `format` | COMBO | Transparent MOV | Transparent MOV, PNG sequence, MP4 composite |  |
| `motion_blur` | COMBO | 3 samples | Off, 3 samples, 5 samples |  |
| `video_file` | STRING |  |  |  |
| `project_json` | STRING |  |  |  Multiline text is supported. |
| `filename_prefix` | STRING | mariotyport |  |  |

### Outputs

| Socket | Type |
|---|---|
| `export_path` | `STRING` |
| `poster` | `IMAGE` |
| `alpha_mask` | `MASK` |
| `project_json` | `STRING` |
