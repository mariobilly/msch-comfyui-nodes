> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# msch-edge-ascii

Animate contour-following ASCII marks over a photo, or apply the effect to an existing video. The main **msch-edge-ascii** node returns a native **VIDEO**. Connect it to **Save Video** to export an MP4.

## Workflows

- **Photo to animated MP4:** drag `workflows/edge_ascii.json` into ComfyUI. Select your photo in Load Image and queue. Defaults: 4 seconds, 24 FPS, yellow strokes, looping flow animation.
- **Video to processed MP4:** drag `workflows/edge_ascii_video_input.json` into ComfyUI. Select a clip in Load Video and queue. The node preserves decoded frame count, source FPS, and audio. This workflow defaults to animation `none`, so marks follow moving content. Select `flow` to animate the marks as well.

The workflows save to `ComfyUI/output/video/msch-edge-ascii_*.mp4`. The `_api.json` files are equivalent API prompts; replace their example input filename before use.

Restart ComfyUI after installation and refresh the browser. Add a new **msch-edge-ascii** node or load the supplied workflow. Nodes already present in older workflows remain image processors, now named **msch-edge-ascii (frames)** to preserve existing connections.

## Animation controls

| Control | Purpose |
|---|---|
| `fps` | Frame rate for a photo or IMAGE batch. VIDEO input retains its source rate. |
| `duration_seconds` | Animation length for one photo. Videos and frame batches retain their length. |
| `animation` | `flow`: traveling brightness waves across the glyph grid. `pulse`: marks fade together. `none`: constant effect per frame. |
| `cycles` | Complete animation cycles over the clip; integer cycles loop smoothly over a still photo. |
| `animation_strength` | Amount of fading; zero disables animation. |

Connect either `image` or `video`. Optional `audio` adds a soundtrack or replaces the video's audio. White in `mask` permits the effect; black excludes it. A single mask broadcasts over source frames. When animating a photo, the photograph stays still and the ASCII marks move.

## Effect controls

Modes: `edge_only` for contour strokes; `mixed` for strokes plus shadow dots; `full_ascii` for dense dots, stripes, and blocks. For the dense screenshot look, use fill amount 1.0 in full ASCII mode.

Start with cell size **16**, line width **1.6**, threshold **0.055**, and color **#FFFF00** on a 400 x 525 image. Double cell size and line width for roughly twice the resolution.

- `edge_threshold`: lower produces more strokes.
- `edge_coherence`: higher removes marks from noisy textures.
- `blur`: smooths contour detection without blurring the photo.
- `line_length`, `line_width`, `color`, `opacity`: style the marks.
- `tone_gamma`: higher selects denser tone glyphs.
- `fill_amount`: full ASCII tone-pattern opacity, or mixed-mode shadow coverage.
- `invert_tones`: reverse brightness when selecting tone patterns.
- `background`: original photo or a solid hex color.

## Installation and requirements

Copy this folder into `ComfyUI/custom_nodes/msch-edge-ascii`. Uses your installed ComfyUI's native VIDEO API and Save Video node, plus its existing PyTorch, NumPy, Pillow, and PyAV packages. No models, fonts, API keys, or VideoHelperSuite dependency are needed.

## Processing and limitations

This is an independent approximation of the supplied EdgeAscii references. Color gradients determine contour directions; geometric glyphs and brightness patterns are composited over the source. Animation is procedural.

Processing runs on CPU. Videos are decoded and the output frame batch is held in memory by the native VIDEO object; use short clips or resize frames upstream for large inputs. Four seconds at 24 FPS and 1024 x 1024 needs about 1.2 GB for output frames alone. There is no optical-flow stabilization; changing video details can cause glyph flicker. Odd width or height is padded by one replicated pixel for H.264 compatibility. Output is SDR RGB, and native decoding uses the source's average frame rate.

The still-image processor remains available as **msch-edge-ascii (frames)** with IMAGE and effect-mask outputs for other workflows.

## Validation

Fourteen tests cover effect rendering, batching, masks, contour orientation, animated frame changes, timing, original video FPS/audio, and an actual H.264 MP4 encode/decode with an audio track. Run tests with ComfyUI's Python and its root on `sys.path`.

`previews/animated_preview.mp4` is an actual four-second render from the supplied photo screenshot. `previews/comparison.png` compares the three static effect modes. The example workflows use ComfyUI's installed Load Video and Save Video nodes.
