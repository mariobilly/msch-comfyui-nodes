# MSCH Pointillism: node reference

Animate color-sampled dots over paper with distortion, ink bleed, grain and frame-hold controls.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## PointillismEffect

**Display name:** Pointillism Effect (Video)  
**Category:** `video/stylize`  
**Output node:** no

Scatter image-color-sampled dots across a paper-like background. Density, radius, distribution and darkness response determine the dot field; ink bleed, distortion, grain and tonal controls shape the print appearance. A still can become an animation through seeded re-scattering, frame holds and frame drops. Returns native VIDEO, the same IMAGE frames and dot-coverage MASK; optional AUDIO accompanies the video.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `image` | IMAGE | — |  | A still image (animated for `frames` frames) or a frame batch. |
| `frames` | INT | 48 | 1 to 4096 | Frames to generate from a still image. Ignored when the input is already a batch. |
| `fps` | FLOAT | 24.0 | 1.0 to 120.0; step 1.0 |  |
| `hold_frames` | INT | 2 | 1 to 30 | Keep each dot layout for this many frames. 1 = new dots every frame, 2-3 = the post's frame-drop stutter. |
| `frame_drop` | FLOAT | 0.0 | 0.0 to 0.9; step 0.01 | Random chance a frame repeats the previous layout (irregular stutter). |
| `saturation` | FLOAT | 1.35 | 0.0 to 3.0; step 0.05 | Boost colours before sampling (the post says: more colour, better). |
| `contrast` | FLOAT | 1.15 | 0.2 to 3.0; step 0.05 |  |
| `density` | FLOAT | 40.0 | 0.5 to 500.0; step 0.5 | Dots per 1000 pixels. 1024x1024 @ 40 = ~42k dots. |
| `point_size` | FLOAT | 2.5 | 0.5 to 64.0; step 0.1 | Dot radius in pixels. |
| `size_variation` | FLOAT | 0.5 | 0.0 to 1.0; step 0.01 | Random +/- radius variation (width variation). |
| `size_by_darkness` | FLOAT | 0.0 | 0.0 to 1.0; step 0.01 | Bigger dots in dark areas, smaller in light (stipple feel). |
| `edge_softness` | FLOAT | 0.3 | 0.0 to 1.0; step 0.01 |  |
| `color_jitter` | FLOAT | 0.05 | 0.0 to 1.0; step 0.01 | Random per-dot colour variation. |
| `dot_opacity` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `distribution` | COMBO | random | random, jittered_grid |  |
| `background` | COMBO | white | white, black, original, custom | white = the post's Hidden image mode. original keeps the photo under the dots. |
| `background_color` | STRING | #FFFFFF |  |  |
| `distortion` | FLOAT | 0.35 | 0.0 to 1.0; step 0.01 | Warps the dots with a paper-fibre field so they stop being perfect circles. |
| `distortion_scale` | FLOAT | 3.5 | 1.0 to 200.0; step 0.5 | Size in px of the warp features. |
| `ink_bleed` | FLOAT | 0.15 | 0.0 to 1.0; step 0.01 | Softens dots like ink soaking into paper. |
| `paper_grain` | FLOAT | 0.12 | 0.0 to 1.0; step 0.01 |  |
| `seed` | INT | 0 | 0 to 18446744073709551615 |  |
| `animate_seed` | BOOLEAN | True |  | Re-scatter the dots over time (the animate-random-seed step). Off = frozen dot layout. |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `audio` | AUDIO | — |  | Optional soundtrack muxed into the video output. |

### Outputs

| Socket | Type |
|---|---|
| `video` | `VIDEO` |
| `frames` | `IMAGE` |
| `dots_mask` | `MASK` |
