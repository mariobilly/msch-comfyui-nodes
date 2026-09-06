# MSCH TimeSlice

Temporal displacement of video bands and cubes with time-offset color ramps, RGB spread and jitter.

This component is included in the **[MSCH Nodes pack](../../README.md)**. Install the pack once; no separate installation is needed.

[Full node reference](docs/NODES.md) · [Workflows and outputs](examples/README.md) · [Installation and optional dependencies](../../README.md#installation)

Requires a multi-frame IMAGE batch for a visible time-displacement effect. A single frame or span_frames=0 passes through unchanged. Band size sets the spatial slices; span_frames sets the temporal spread. Audio and playback FPS stay with the external video loading/encoding nodes.
