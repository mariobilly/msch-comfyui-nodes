# H3 Generation

Model-dependent generation template; not a verified completed video render. Install comfyui-minimax-h3-audio-T8 and its compatible checkpoints, then select the actual diffusion model, text encoder, LoRA and both VAEs in the loader nodes. SELECT_* values are explicit placeholders. Review resolution against the model bucket configuration. Copy inputs/beat.wav into ComfyUI/input. This template uses native ComfyUI loaders and the separate H3 integration; the 4-step setting assumes the matching turbo LoRA.

Load `h3_generation.json` on the ComfyUI canvas. `h3_generation_api.json` is a prompt for the `/prompt` API, not a canvas workflow. Copy the required files from `inputs/` into `ComfyUI/input/` and reselect them in the load nodes.
