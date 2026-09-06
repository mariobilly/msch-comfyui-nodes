# MSCH Nodes

**One install. All 35 nodes.** Video effects, slideshows, typography, lyric synchronization and MiniMax H3 sequencing, plus the MSCH theme and editor bridge.

[Showcase: videos and workflows](SHOWCASE.md) · [Every node explained](docs/NODES.md) · [Migrate from the separate packs](MIGRATION.md)

Install **MSCH Nodes** once. Future nodes and improvements arrive through updates to this same pack. Components are organized internally; they do not need separate installations.

## Installation

In ComfyUI Manager, search for **MSCH Nodes** / `msch-comfyui-nodes`. The unified Registry submission is tracked in [PUBLISHING.md](PUBLISHING.md). If the catalog has not indexed it yet, use Manager's Git URL installation with:

```text
https://github.com/mariobilly/msch-comfyui-nodes
```

Or clone it into `ComfyUI/custom_nodes`:

```bash
git clone https://github.com/mariobilly/msch-comfyui-nodes.git
```

Install requirements with the same Python used by ComfyUI, then restart ComfyUI and refresh the browser:

```bash
python -m pip install -r ComfyUI/custom_nodes/msch-comfyui-nodes/requirements.txt
```

For Windows portable, run this from `ComfyUI_windows_portable`:

```powershell
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\msch-comfyui-nodes\requirements.txt
```

Already installed the old separate MSCH packs? Follow [MIGRATION.md](MIGRATION.md) to switch without duplicate nodes. Existing node IDs and workflow connections are preserved.

## Optional features

- **Typort rendering:** install `requirements-typort.txt`, then run `python -m playwright install chromium` using ComfyUI's Python. The typography node registers without Chromium; rendering requires it.
- **A2V generation:** install the separate `comfyui-minimax-h3-audio-T8` integration and compatible H3 model files. The other components do not need H3 or its weights.
- **Precise Puppet Face tracking:** optional ONNX runtime and separately supplied face models; the approximate fallback remains available.
- **Advanced slideshow framing:** optional dependencies are in `requirements-advanced.txt`.
- **WhisperX alignment and Typort stem separation:** optional integrations; see the respective component references. Lyrics have an explicitly documented even-timing fallback.

Each component loads independently. A missing optional dependency is logged and does not prevent unrelated components from loading. No models or Chromium are downloaded automatically during startup.

## Included components

| Component | Nodes | Description | Examples |
|---|---:|---|---|
| [MSCH A2V](components/a2v/docs/NODES.md) | 7 | Beat-synced prompt sequencing, shot planning, MiniMax H3 sampling, assembly and pixel upscaling for music videos. | [Workflows and results](components/a2v/examples/README.md) |
| [MSCH Code Matrix](components/code_matrix/docs/NODES.md) | 1 | Convert images and video frames into ASCII portraits, binary art and animated Matrix-style glyph patterns. | [Workflows and results](components/code_matrix/examples/README.md) |
| [MSCH Edge ASCII](components/edge_ascii/docs/NODES.md) | 2 | Contour-aligned ASCII strokes, halftone fills and animated marks for photos and native ComfyUI video. | [Workflows and results](components/edge_ascii/examples/README.md) |
| [MSCH Lyric Sync](components/lyric_sync/docs/NODES.md) | 4 | Align pasted lyrics to audio and render bilingual captions or animated lyric mosaics with editable color palettes. | [Workflows and results](components/lyric_sync/examples/README.md) |
| [MSCH MCP Bridge](components/mcp_bridge/docs/NODES.md) | 0 | Local ComfyUI browser bridge for changing widget values, setting node modes and reading the current graph. | [Workflows and results](components/mcp_bridge/examples/README.md) |
| [MSCH Pointillism](components/pointillism/docs/NODES.md) | 1 | Animate color-sampled dots over paper with distortion, ink bleed, grain and frame-hold controls. | [Workflows and results](components/pointillism/examples/README.md) |
| [MSCH Puppet Face](components/puppet_face/docs/NODES.md) | 3 | Face landmark and animated cursor overlays with self-contained OpenCV video loading and MP4 saving. | [Workflows and results](components/puppet_face/examples/README.md) |
| [MSCH Scan FX](components/scanfx/docs/NODES.md) | 1 | Stack up to eight thermal, night-vision, hologram, HUD, radar, glitch and other scan effects inside an optional mask. | [Workflows and results](components/scanfx/examples/README.md) |
| [MSCH Slideshow](components/slideshow/docs/NODES.md) | 7 | Photo slideshow studio with animated layouts, beat analysis, subject framing, editable shot plans and streamed video export. | [Workflows and results](components/slideshow/examples/README.md) |
| [MSCH Slideshow Forge](components/slideshow_forge/docs/NODES.md) | 2 | Build editable photo timelines and render procedural Ken Burns motion and transitions using PyTorch and Kornia. | [Workflows and results](components/slideshow_forge/examples/README.md) |
| [MSCH Synkit FX](components/synkitfx/docs/NODES.md) | 2 | Animated metaball halftones and feature-tracking HUD boxes with labels, connectors, native VIDEO and overlay masks. | [Workflows and results](components/synkitfx/examples/README.md) |
| [MSCH Theme](components/theme/docs/NODES.md) | 0 | Apply the MSCH carbon, steel, bone and acid-accent palette to compatible custom node cards. | [Workflows and results](components/theme/examples/README.md) |
| [MSCH TimeSlice](components/timeslice/docs/NODES.md) | 1 | Temporal displacement of video bands and cubes with time-offset color ramps, RGB spread and jitter. | [Workflows and results](components/timeslice/examples/README.md) |
| [MSCH Typort](components/typort/docs/NODES.md) | 1 | Layered animated typography studio with Arabic text, keyframes, audio reactions and transparent or composite exports. | [Workflows and results](components/typort/examples/README.md) |
| [MSCH Warp Wiggle](components/warp_wiggle/docs/NODES.md) | 3 | Warped transitions between video clips, animated single-clip distortion and matching HUD overlays. | [Workflows and results](components/warp_wiggle/examples/README.md) |

## Updates and new nodes

Use Manager to update **MSCH Nodes**, then restart ComfyUI. All components update together. New nodes are added inside this repository and released under the same Registry package. See [CONTRIBUTING.md](CONTRIBUTING.md) for the component layout and release checklist.

## Examples and validation

The [showcase](SHOWCASE.md) includes 33 videos, 62 images, five project/render records and 20 supplied API workflows, organized by component. Earlier procedural examples remain available as well. API workflows need the source inputs and model selections described in their setup notes.

The unified pack was loaded through ComfyUI's actual custom-node loader: all 35 node IDs registered under one package, all 15 components loaded, and the six component frontends were registered through one bootstrap. A procedural render and the migration/failure-isolation tests passed. See [VALIDATION.md](VALIDATION.md) for the scope of verification.

## License

Node code uses [MIT](LICENSE). Component license notices, bundled font/icon licenses and media notes are retained in their folders. Optional models keep their own licenses.
