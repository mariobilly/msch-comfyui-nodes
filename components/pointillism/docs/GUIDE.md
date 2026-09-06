> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# ComfyUI-Pointillism

One node, **Pointillism Effect (Video)** (category `video/stylize`), that recreates the
effect.app "Pointillism" look as a video: thousands of small colour-sampled dots
scattered over white paper, re-scattered every frame, with size variation, paper
distortion, grain and a frame-drop stutter.

Pure PyTorch, runs on the GPU, no extra dependencies. About 10 ms per 1024px
frame after warm-up, so a 2 second clip renders in well under a second.

## Install

Already in place at `ComfyUI/custom_nodes/ComfyUI-Pointillism`.
Restart ComfyUI and search for **Pointillism Effect**. Drag `example_workflow.json`
onto the canvas for a ready-made Load Image -> Pointillism -> Save Video chain.

## Inputs / outputs

| Socket | Type | Notes |
|---|---|---|
| image | IMAGE | a still image (animated for `frames` frames) or a frame batch from Load Video |
| audio | AUDIO, optional | muxed into the video output |
| video | VIDEO | plug straight into **Save Video** |
| frames | IMAGE | the same frames as a batch, for Create Video / Video Combine / further nodes |
| dots_mask | MASK | per-frame dot coverage (1 = dot, 0 = paper) for compositing |

Odd-sized inputs are trimmed by one pixel so H.264 can encode them.

## Parameters, mapped to the post's steps

| Post step | Parameter(s) | Default |
|---|---|---|
| "Increase saturation and contrast" | `saturation`, `contrast` | 1.35, 1.15 |
| "Add a scatter effect" | `density` (dots per 1000 px), `distribution` | 40, random |
| "Image mode Hidden, dot colour Original" | `background` = white | white |
| "Reduce point size, add width variation" | `point_size` (radius px), `size_variation` | 2.5, 0.5 |
| "Increase density" | `density` | 40 (try 60 to 120) |
| "Paper texture + distortion" | `distortion`, `distortion_scale`, `ink_bleed`, `paper_grain` | 0.35, 3.5, 0.15, 0.12 |
| "Animate the random seed" | `animate_seed`, `frames`, `fps` | on, 48, 24 |
| "Frame drop effect" | `hold_frames`, `frame_drop` | 2, 0 |

Animation controls:

- `frames` and `fps`: length of the clip made from a still. Ignored when the input is already a batch.
- `hold_frames`: each dot layout is held this many frames. 1 = new dots every frame (fast flicker), 2 or 3 = the post's steppy frame-drop feel at 24 fps.
- `frame_drop`: random chance that a scheduled re-scatter is skipped, for an irregular stutter.
- `animate_seed` off freezes the dot layout across the whole clip.

Extras not in the post:

- `background` = original keeps the photo under the dots (the "by default" look in slide 3).
- `background` = black or custom (`background_color` hex) for dark paper.
- `size_by_darkness` grows dots in shadows and shrinks them in highlights for a stipple look.
- `color_jitter` adds per-dot colour noise.
- `edge_softness` controls anti-aliasing of the dot edges.
- `dot_opacity` lets the paper show through.
- `distribution` = jittered_grid gives even coverage with no clumps.

## Recipes

- Post look (Burano houses): defaults.
- Clean vector dots (slide 6): `distortion` 0, `ink_bleed` 0, `paper_grain` 0.
- Big confetti (slide 4): `point_size` 8, `density` 5, `size_variation` 0.3, `distortion` 0.
- Heavy ink on paper: `density` 90, `point_size` 2, `distortion` 0.7, `ink_bleed` 0.3.
- Stylise an existing clip: Load Video -> Pointillism Effect -> Save Video, `hold_frames` 1.

Frames are rendered one at a time so memory use stays flat for long clips.
