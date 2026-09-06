# MSCH Edge ASCII: node reference

Contour-aligned ASCII strokes, halftone fills and animated marks for photos and native ComfyUI video.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## EdgeASCII

**Display name:** msch-edge-ascii (frames)  
**Category:** `image/effects`  
**Output node:** no

Analyze local image gradients and align ASCII strokes with contours. Mixed and full-ASCII modes add tone-based fills. Cell size, line dimensions, thresholds, coherence and blur determine the mark field; colors and opacity control compositing. An optional MASK restricts coverage. Returns an IMAGE batch and retains the legacy node identifier for existing workflows.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `image` | IMAGE | — |  |  |
| `mode` | COMBO | edge_only | edge_only, full_ascii, mixed |  |
| `cell_size` | INT | 16 | 4 to 128; step 1 | Grid spacing in pixels. Scale this with image resolution. |
| `color` | STRING | #FFFF00 |  |  |
| `opacity` | FLOAT | 1.0 | 0.0 to 1.0; step 0.05 |  |
| `line_width` | FLOAT | 1.6 | 0.5 to 16.0; step 0.1 |  |
| `line_length` | FLOAT | 0.85 | 0.1 to 1.0; step 0.05 |  |
| `edge_threshold` | FLOAT | 0.055 | 0.0 to 1.0; step 0.005 | Lower values create more strokes; higher values keep stronger contours. |
| `edge_coherence` | FLOAT | 0.25 | 0.0 to 1.0; step 0.05 | Raise to remove strokes from noisy areas with conflicting directions. |
| `blur` | FLOAT | 1.2 | 0.0 to 12.0; step 0.1 | Smooth the detection image only; the original photo stays sharp. |
| `tone_gamma` | FLOAT | 1.6 | 0.1 to 4.0; step 0.1 |  |
| `fill_amount` | FLOAT | 0.5 | 0.0 to 1.0; step 0.05 | Full ASCII: tone-pattern opacity (use 1 for dense yellow). Mixed: shadow coverage. Edge only: unused. |
| `invert_tones` | BOOLEAN | False |  |  |
| `background` | COMBO | original | original, solid |  |
| `background_color` | STRING | #000000 |  |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `mask` | MASK | — |  | White permits the effect, black excludes it. Single mask broadcasts over the batch. |

### Outputs

| Socket | Type |
|---|---|
| `image` | `IMAGE` |
| `effect_mask` | `MASK` |

## MschEdgeASCIIVideo

**Display name:** msch-edge-ascii  
**Category:** `video/effects`  
**Output node:** no

Animate contour-following ASCII over a still image or process a native VIDEO. For a still, duration_seconds and FPS define the animation. For video, source frame count, FPS and audio are retained unless audio is explicitly replaced. Flow and pulse animate marks independently of content motion; none uses a static treatment per frame. Returns native VIDEO for Save Video.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `fps` | FLOAT | 24.0 | 1.0 to 120.0; step 0.01 | Frame rate for a still photo or IMAGE batch. VIDEO input retains its own FPS. |
| `duration_seconds` | FLOAT | 4.0 | 0.1 to 60.0; step 0.1 | Duration when animating one photo. Existing videos and frame batches retain their length. |
| `animation` | COMBO | flow | flow, pulse, none |  |
| `cycles` | INT | 1 | 1 to 32 | Complete animation cycles over the clip; integer cycles loop smoothly on a still photo. |
| `animation_strength` | FLOAT | 0.85 | 0.0 to 1.0; step 0.05 |  |
| `mode` | COMBO | edge_only | edge_only, full_ascii, mixed |  |
| `cell_size` | INT | 16 | 4 to 128; step 1 | Grid spacing in pixels. Scale this with image resolution. |
| `color` | STRING | #FFFF00 |  |  |
| `opacity` | FLOAT | 1.0 | 0.0 to 1.0; step 0.05 |  |
| `line_width` | FLOAT | 1.6 | 0.5 to 16.0; step 0.1 |  |
| `line_length` | FLOAT | 0.85 | 0.1 to 1.0; step 0.05 |  |
| `edge_threshold` | FLOAT | 0.055 | 0.0 to 1.0; step 0.005 | Lower values create more strokes; higher values keep stronger contours. |
| `edge_coherence` | FLOAT | 0.25 | 0.0 to 1.0; step 0.05 | Raise to remove strokes from noisy areas with conflicting directions. |
| `blur` | FLOAT | 1.2 | 0.0 to 12.0; step 0.1 | Smooth the detection image only; the original photo stays sharp. |
| `tone_gamma` | FLOAT | 1.6 | 0.1 to 4.0; step 0.1 |  |
| `fill_amount` | FLOAT | 0.5 | 0.0 to 1.0; step 0.05 | Full ASCII: tone-pattern opacity (use 1 for dense yellow). Mixed: shadow coverage. Edge only: unused. |
| `invert_tones` | BOOLEAN | False |  |  |
| `background` | COMBO | original | original, solid |  |
| `background_color` | STRING | #000000 |  |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `image` | IMAGE | — |  | Connect a single photo to animate, or a batch of video frames. Connect either image or video. |
| `video` | VIDEO | — |  | Connect Load Video; its FPS, frame count and audio are preserved. |
| `audio` | AUDIO | — |  | Optional soundtrack; overrides audio from VIDEO input. |
| `mask` | MASK | — |  | White permits the effect, black excludes it. Single mask broadcasts over the batch. |

### Outputs

| Socket | Type |
|---|---|
| `video` | `VIDEO` |
