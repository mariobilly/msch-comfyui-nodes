# MSCH Slideshow Forge: node reference

Build editable photo timelines and render procedural Ken Burns motion and transitions using PyTorch and Kornia.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## SlideshowForge_Director

**Display name:** Slideshow Director  
**Category:** `SlideshowForge`  
**Output node:** no

Turn an image batch into an editable timeline containing source indices, motion, duration and transition choices. Choose a style preset and total-duration, per-image or beat-sync timing. AUDIO is required for beat-sync mode. A supplied timeline_json_in can replace generation after validation. Returns timeline JSON, source image count and audio for the encoder.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `preset` | COMBO | classic_ken_burns | classic_ken_burns, dynamic_wipes, slow_cinematic |  |
| `duration_mode` | COMBO | total_duration | total_duration, per_image_duration, beat_sync |  |
| `total_duration` | FLOAT | 30.0 | 1.0 to 3600.0; step 0.5 |  |
| `per_image_duration` | FLOAT | 3.0 | 0.3 to 60.0; step 0.1 |  |
| `fps` | INT | 30 | 1 to 120 |  |
| `seed` | INT | 0 | 0 to 18446744073709551615 |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `audio` | AUDIO | — |  |  |
| `beats_per_image` | INT | 2 | 1 to 32 |  |
| `timeline_json_in` | STRING |  |  |  Multiline text is supported. |
| `on_invalid_json` | COMBO | error | error, regenerate |  |
| `shuffle_order` | BOOLEAN | False |  |  |
| `loop` | BOOLEAN | False |  |  |
| `canvas_fit` | COMBO | cover | cover, contain_blur_bg, contain_black_bg |  |
| `output_width` | INT | 0 | 0 to 8192 |  |
| `output_height` | INT | 0 | 0 to 8192 |  |

### Outputs

| Socket | Type |
|---|---|
| `timeline_json` | `STRING` |
| `image_count` | `INT` |
| `audio` | `AUDIO` |

## SlideshowForge_GPURenderer

**Display name:** GPU Motion Renderer  
**Category:** `SlideshowForge`  
**Output node:** no

Render the Director's timeline against the same source image batch using PyTorch/Kornia transforms and transitions. Reads canvas and segment settings from timeline_json and samples animation at the requested FPS. Outputs RGB IMAGE frames; connect them to Create Video or VideoHelperSuite. Rendering is procedural and requires no diffusion checkpoint.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `timeline_json` | STRING | — |  |  Connect this value through an input socket. |
| `fps` | INT | 30 | 1 to 120 |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `render_chunk_frames` | INT | 64 | 8 to 512 |  |
| `precision` | COMBO | fp16 | fp16, fp32 |  |
| `device` | COMBO | auto | auto, cuda, cpu |  |
| `max_output_bytes_gb` | FLOAT | 8.0 | 0.5 to 256.0 |  |

### Outputs

| Socket | Type |
|---|---|
| `IMAGE` | `IMAGE` |
