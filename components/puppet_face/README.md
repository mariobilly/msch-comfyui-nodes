# MSCH Puppet Face

Face landmark and animated cursor overlays with self-contained OpenCV video loading and MP4 saving.

This component is included in the **[MSCH Nodes pack](../../README.md)**. Install the pack once; no separate installation is needed.

[Full node reference](docs/NODES.md) · [Workflows and outputs](examples/README.md) · [Installation and optional dependencies](../../README.md#installation)

Includes three nodes: load video, overlay and save video. Optional ONNX tracking uses onnxruntime plus SCRFD and 106-point landmark models in ComfyUI/models/insightface/models/antelopev2. No models are bundled. Without a usable precise tracker the overlay falls back to approximate face-box geometry. The included video loader/saver does not preserve source audio. Consult the model distributor's license before using optional model weights.
