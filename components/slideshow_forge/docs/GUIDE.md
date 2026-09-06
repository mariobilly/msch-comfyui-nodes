> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# ComfyUI-SlideshowForge

Procedural, non-AI slideshow generator for ComfyUI. Turns a batch of images into a
randomized, style-directed animated clip (Ken Burns pans/zooms + transitions) rendered
entirely on your GPU via `torch`/`kornia` -- no diffusion model involved. Two nodes:

- **Slideshow Director** -- images + style preset + duration + seed -> an editable
  timeline JSON (per-segment image, duration, motion, transition).
- **GPU Motion Renderer** -- images + timeline JSON -> a rendered `IMAGE` batch. Feed
  this into `VHS_VideoCombine` (from ComfyUI-VideoHelperSuite) to encode to video.

## Quick start

`VHS_LoadImagesFromPath` -> **Slideshow Director** -> **GPU Motion Renderer** ->
`VHS_VideoCombine`.

## Presets (v1)

- `classic_ken_burns` -- gentle zoom/pan, crossfades.
- `dynamic_wipes` -- faster cuts, directional/diagonal wipes.
- `slow_cinematic` -- slow subtle motion, long crossfades/blur dissolves.

## Editing a generated timeline

Copy the `timeline_json` output, hand-edit any segment's motion/transition/duration,
and paste it into the Director's `timeline_json_in` input -- it will be validated and
re-rendered as-is instead of generating a new random timeline. `on_invalid_json`
controls whether an invalid edit raises an error (default) or falls back to a fresh
random generation.

## Known v1 limitations

- **No audio/beat-reactive sync** -- explicitly out of scope for this build.
- **Mixed portrait/landscape input**: standard image loaders (including VHS's) resize
  and center-crop every image to one common size before this pack ever sees the batch.
  `canvas_fit=contain_blur_bg`/`contain_black_bg` only produce a true letterboxed look
  if your upstream loader/resize step pads (rather than crops) to a common canvas.
- **Render length ceiling**: the final frame batch is a single CPU tensor (required by
  `VHS_VideoCombine`'s API), so very long/high-res renders can be memory-prohibitive.
  `max_output_bytes_gb` on GPU Motion Renderer fails fast with a clear error before
  rendering rather than hanging/OOMing. Realistic v1 ceiling is roughly a few minutes
  at 1080p30.
