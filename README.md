# MSCH ComfyUI Nodes

A collection of 15 independently installable ComfyUI packages by [mariobilly](https://github.com/mariobilly): 35 graph nodes plus two browser extensions.

Each repository includes installation instructions, a complete node reference, examples, MIT project licensing and GitHub validation/publishing workflows. This repository is the collection index; install the individual packages linked below.

| Package | Nodes | Purpose | Documentation |
|---|---:|---|---|
| [MSCH A2V](https://github.com/mariobilly/msch-a2v) | 7 | Beat-synced prompt sequencing, shot planning, MiniMax H3 sampling, assembly and pixel upscaling for music videos. | [Reference](https://github.com/mariobilly/msch-a2v/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-a2v/tree/main/examples) |
| [MSCH Code Matrix](https://github.com/mariobilly/msch-code-matrix) | 1 | Convert images and video frames into ASCII portraits, binary art and animated Matrix-style glyph patterns. | [Reference](https://github.com/mariobilly/msch-code-matrix/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-code-matrix/tree/main/examples) |
| [MSCH Edge ASCII](https://github.com/mariobilly/msch-edge-ascii) | 2 | Contour-aligned ASCII strokes, halftone fills and animated marks for photos and native ComfyUI video. | [Reference](https://github.com/mariobilly/msch-edge-ascii/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-edge-ascii/tree/main/examples) |
| [MSCH Lyric Sync](https://github.com/mariobilly/msch-lyric-sync) | 4 | Align pasted lyrics to audio and render bilingual captions or animated lyric mosaics with editable color palettes. | [Reference](https://github.com/mariobilly/msch-lyric-sync/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-lyric-sync/tree/main/examples) |
| [MSCH MCP Bridge](https://github.com/mariobilly/msch-mcp-bridge) | 0 | Local ComfyUI browser bridge for changing widget values, setting node modes and reading the current graph. | [Reference](https://github.com/mariobilly/msch-mcp-bridge/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-mcp-bridge/tree/main/examples) |
| [MSCH Pointillism](https://github.com/mariobilly/msch-pointillism) | 1 | Animate color-sampled dots over paper with distortion, ink bleed, grain and frame-hold controls. | [Reference](https://github.com/mariobilly/msch-pointillism/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-pointillism/tree/main/examples) |
| [MSCH Puppet Face](https://github.com/mariobilly/msch-puppet-face) | 3 | Face landmark and animated cursor overlays with self-contained OpenCV video loading and MP4 saving. | [Reference](https://github.com/mariobilly/msch-puppet-face/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-puppet-face/tree/main/examples) |
| [MSCH Scan FX](https://github.com/mariobilly/msch-scanfx) | 1 | Stack up to eight thermal, night-vision, hologram, HUD, radar, glitch and other scan effects inside an optional mask. | [Reference](https://github.com/mariobilly/msch-scanfx/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-scanfx/tree/main/examples) |
| [MSCH Slideshow](https://github.com/mariobilly/msch-slideshow) | 7 | Photo slideshow studio with animated layouts, beat analysis, subject framing, editable shot plans and streamed video export. | [Reference](https://github.com/mariobilly/msch-slideshow/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-slideshow/tree/main/examples) |
| [MSCH Slideshow Forge](https://github.com/mariobilly/msch-slideshow-forge) | 2 | Build editable photo timelines and render procedural Ken Burns motion and transitions using PyTorch and Kornia. | [Reference](https://github.com/mariobilly/msch-slideshow-forge/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-slideshow-forge/tree/main/examples) |
| [MSCH Synkit FX](https://github.com/mariobilly/msch-synkitfx) | 2 | Animated metaball halftones and feature-tracking HUD boxes with labels, connectors, native VIDEO and overlay masks. | [Reference](https://github.com/mariobilly/msch-synkitfx/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-synkitfx/tree/main/examples) |
| [MSCH Theme](https://github.com/mariobilly/msch-theme) | 0 | Apply the MSCH carbon, steel, bone and acid-accent palette to compatible custom node cards. | [Reference](https://github.com/mariobilly/msch-theme/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-theme/tree/main/examples) |
| [MSCH TimeSlice](https://github.com/mariobilly/msch-timeslice) | 1 | Temporal displacement of video bands and cubes with time-offset color ramps, RGB spread and jitter. | [Reference](https://github.com/mariobilly/msch-timeslice/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-timeslice/tree/main/examples) |
| [MSCH Typort](https://github.com/mariobilly/msch-typort) | 1 | Layered animated typography studio with Arabic text, keyframes, audio reactions and transparent or composite exports. | [Reference](https://github.com/mariobilly/msch-typort/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-typort/tree/main/examples) |
| [MSCH Warp Wiggle](https://github.com/mariobilly/msch-warp-wiggle) | 3 | Warped transitions between video clips, animated single-clip distortion and matching HUD overlays. | [Reference](https://github.com/mariobilly/msch-warp-wiggle/blob/main/docs/NODES.md) · [Examples](https://github.com/mariobilly/msch-warp-wiggle/tree/main/examples) |

## Example results

**[Browse the new MSCH Node Showcase](SHOWCASE.md)** — rendered videos, stills and API workflows organized across 14 packages.

Twelve visual-effects packages include actual rendered MP4/PNG demos with original geometric inputs. A2V additionally includes a [completed H3 model-generation demo](https://github.com/mariobilly/msch-a2v/blob/main/examples/h3_rendered_demo.md), exact workflow and verified compiled schedule data. Theme and MCP Bridge affect the editor and do not render video.

## Installation

Clone the desired repository into `ComfyUI/custom_nodes`, install its requirements with ComfyUI's Python, then restart ComfyUI and refresh the browser. Read each package's requirements before loading workflows; Typort also needs Playwright Chromium, and A2V needs the separate H3 integration and model files.

## ComfyUI Manager and Registry

Manager node-list registration: [PR #3247 submitted](https://github.com/Comfy-Org/ComfyUI-Manager/pull/3247), pending maintainer acceptance. All 15 packages uploaded version `0.1.0` successfully under Registry publisher `mariobilly` on 2026-09-06. All publishing workflows passed, and every uploaded ZIP was downloaded and checked. Registry reported `Pending` for these versions at verification; Manager installation availability is not yet confirmed. See [Registry releases and workflow results](registry-releases.json).

See [manager-entries.json](manager-entries.json) for the proposed database entries.

## Validation

- All 15 packages imported and exposed their expected 35 node schemas.
- All 15 runnable generated API examples passed the installed ComfyUI prompt validator.
- A2V: 108 existing tests passed.
- ScanFX: two regression tests passed after fixing OpenCV 5 text rendering.
- Every package passed release syntax, JSON graph and metadata checks, including all 15 hosted GitHub Actions runs.
- Actual demo renders cover the twelve visual-effects packages and an A2V INT4 H3 generation on a 12 GB GPU. Pixel-upscale refinement, other model configurations and every browser interaction were not exhaustively tested.

Project code uses MIT licensing. Bundled fonts/icons and optional models retain their respective licenses.
