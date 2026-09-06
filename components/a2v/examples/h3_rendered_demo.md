# Verified H3 generation demo

[Rendered MP4](results/h3_demo.mp4) · [Still preview](results/h3_demo.png) · [Render record](results/h3_demo.json)

This example completed the full A2V workflow: audio/schedule loading, H3 shot planning, four-step model sampling, VAE decoding, assembly and video saving. It was rendered at 256 × 256 on a 12 GB RTX 4070 SUPER using the installed INT4 models, with a two-second / 48-frame output at 24 FPS. It is a small functional example, not a high-resolution quality benchmark.

Load `h3_rendered_demo.json` on the canvas, copy `inputs/beat.wav` to `ComfyUI/input`, and select your local files for the model loaders. `h3_rendered_demo_api.json` is the corresponding API prompt.

Required files used in this render:

- `minimax_h3_fl2va_pruned_int4_convrot.safetensors`
- `qwen3vl_32b_minimax_h3_int4_convrot.safetensors`
- `minimax_h3_fl2va_4step_lora.safetensors` (selected through the bypass LoRA loader)
- `minimax_h3_video_vae_fp16.safetensors`
- `minimax_h3_audio_vae_fp32.safetensors`

Model weights are not bundled. The separate `comfyui-minimax-h3-audio-T8` integration must be installed. A2V samples H3's minimum trained frame bucket and trims the assembled output to the requested schedule. The soundtrack is an original synthetic beat track, not speech or a song. Pixel-upscale refinement is provided as a separate template and was not executed for this demo.
