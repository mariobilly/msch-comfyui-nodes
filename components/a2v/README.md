# MSCH A2V

Beat-synced prompt sequencing, shot planning, MiniMax H3 sampling, assembly and pixel upscaling for music videos.

This component is included in the **[MSCH Nodes pack](../../README.md)**. Install the pack once; no separate installation is needed.

[Full node reference](docs/NODES.md) · [Workflows and outputs](examples/README.md) · [Installation and optional dependencies](../../README.md#installation)

Requires the separate comfyui-minimax-h3-audio-T8 pack and compatible MiniMax H3 model, text encoder, video VAE and audio VAE. Model files are not bundled. The sequencer creates timing and prompts; the H3 models generate the video. Generation depends on your GPU, model setup and source audio.
