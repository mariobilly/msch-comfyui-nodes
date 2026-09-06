# MSCH Warp Wiggle

Warped transitions between video clips, animated single-clip distortion and matching HUD overlays.

This component is included in the **[MSCH Nodes pack](../../README.md)**. Install the pack once; no separate installation is needed.

[Full node reference](docs/NODES.md) · [Workflows and outputs](examples/README.md) · [Installation and optional dependencies](../../README.md#installation)

All three nodes process IMAGE batches. For transitions, B is resized to A and the output overlaps transition_frames. Keep source frame rates consistent and connect soundtrack audio separately to the encoder. Stylize applies the effect to one clip; HUD Overlay can be used independently.
