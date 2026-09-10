# MSCH Lyric Sync

Align pasted lyrics to audio and render bilingual captions or animated lyric mosaics with editable color palettes.

This component is included in the **[MSCH Nodes pack](../../README.md)**. Install the pack once; no separate installation is needed.

[Full node reference](docs/NODES.md) · [Workflows and outputs](examples/README.md) · [Installation and optional dependencies](../../README.md#installation)

WhisperX is optional and runs as a separate command-line program. Put whisperx on the host PATH; the known per-user Python 3.13 installation is also checked on Windows. The legacy whisperx_exe widget is ignored. If alignment is unavailable or fails, lines receive evenly distributed timing; that fallback is not measured vocal synchronization. Set font_path to an installed Arabic-capable font for Arabic text. Image effects require an explicit matching frame_rate.
