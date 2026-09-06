# MSCH A2V showcase

Examples supplied by Mario from the MSCH Node Showcase collection. The output files are preserved as supplied.

![Featured example](outputs/beat_synced_h3_motel_00001-audio_preview.jpg)

Audio-beat-synced prompt sequencer for MiniMax H3: Beat Prompt Sequencer -> Shot Planner -> Beat KSampler -> Shot Assembler, with an optional pixel-upscale second pass.

- beat_synced_h3_motel.mp4 - one prompt block spanning the detected beat grid of an 8 s excerpt, rendered at 512x288 with the int4 ref2va checkpoint

## Gallery

Click a video preview to open its file on GitHub, or use the download link.

### Beat synced h3 motel

[![Beat synced h3 motel](outputs/beat_synced_h3_motel_00001-audio_preview.jpg)](outputs/beat_synced_h3_motel_00001-audio.mp4)

[Open MP4](outputs/beat_synced_h3_motel_00001-audio.mp4) · [Download original](https://github.com/mariobilly/msch-comfyui-nodes/raw/refs/heads/main/components/a2v/examples/showcase/outputs/beat_synced_h3_motel_00001-audio.mp4)

## API workflows

These JSON files are ComfyUI API prompts, not canvas-format workflows. Send one as the `prompt` field of a `/prompt` request, or use a tool that accepts API workflows. A canvas importer may require conversion.

Choose your own source media and installed models before running. Source photos, video clips, audio and model weights are not bundled in this showcase. The supplied render settings and connections are retained; machine-specific absolute paths in the API copies use `INPUT_ROOT/` or `LOCAL_FILES/` placeholders. Replace these with paths valid on your computer.

- [a2v_api.json](workflows_api/a2v_api.json): `CLIPLoader`, `MiniMaxChunkFeedForward`, `MiniMaxLowVRAMAttention`, `MschA2V_BeatKSampler`, `MschA2V_BeatPromptSequencer`, `MschA2V_ShotAssembler`, `MschA2V_ShotPlanner`, `UNETLoader`, `VAELoader`, `VHS_VideoCombine`.

### Input files and models

| Workflow | Node | Input | Source selection |
|---|---|---|---|
| `a2v_api.json` | `1` | `audio_path` | `msch_song_8s.mp3` |
| `a2v_api.json` | `2` | `unet_name` | `minimax_h3_ref2va_pruned_int4_convrot.safetensors` |
| `a2v_api.json` | `5` | `clip_name` | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` |
| `a2v_api.json` | `6` | `vae_name` | `minimax_h3_video_vae_fp16.safetensors` |
| `a2v_api.json` | `7` | `vae_name` | `minimax_h3_audio_vae_fp32.safetensors` |

Install ComfyUI-VideoHelperSuite for the `VHS_*` loader/combine nodes.

The A2V workflow also needs the MiniMax H3 integration that provides `MiniMaxLowVRAMAttention` and `MiniMaxChunkFeedForward`, plus the model files named above.

## Source notes

The collection notes identify images from the Jim Morrison image library, Mario’s clips, and the Suno track “Crushing Syncopation”. Those source assets are not included separately. The rendered media is supplied as showcase material; the repository’s MIT license describes the node code and does not establish a separate license for underlying media.
