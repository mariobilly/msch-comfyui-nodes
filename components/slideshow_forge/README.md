# MSCH Slideshow Forge

Build editable photo timelines and render procedural Ken Burns motion and transitions using PyTorch and Kornia.

This component is included in the **[MSCH Nodes pack](../../README.md)**. Install the pack once; no separate installation is needed.

[Full node reference](docs/NODES.md) · [Workflows and outputs](examples/README.md) · [Installation and optional dependencies](../../README.md#installation)

The Director outputs timeline JSON, image count and audio; the GPU renderer outputs IMAGE frames. Beat-sync mode requires AUDIO. Use the same source image batch for both nodes. This is a procedural renderer and does not require diffusion models.
