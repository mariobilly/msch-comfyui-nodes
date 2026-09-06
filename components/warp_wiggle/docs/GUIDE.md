> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# ComfyUI-WarpWiggle

Two custom nodes for a **TimeSlice-style "warp & wiggle" transition** between two
video clips, plus a matching **HUD overlay** (crosshairs, colored bars, corner
brackets, glitch text). Inspired by the @thesystms TimeSlice + HUD look.

Both nodes are **IMAGE in / IMAGE out**, so they drop straight into a
VideoHelperSuite (VHS) workflow.

## Install
Folder lives in `ComfyUI/custom_nodes/ComfyUI-WarpWiggle`. **Restart ComfyUI**,
then find the nodes under the **WarpWiggle** category (right-click → Add Node →
WarpWiggle, or double-click search "WarpWiggle" / "HUD").

No extra dependencies — uses torch + Pillow, both already in ComfyUI.

## Workflow (with VideoHelperSuite)
```
VHS Load Video (clip A) ──IMAGE──┐
                                  ├──► WarpWiggle Transition ──► HUD Overlay ──► VHS Video Combine
VHS Load Video (clip B) ──IMAGE──┘
```
- Wire each `Load Video`'s **IMAGE** output into `images_a` / `images_b`.
- `WarpWiggle Transition` outputs ALL of A + the warped overlap + ALL of B,
  i.e. `len(A) + len(B) - transition_frames` frames.
- `HUD Overlay` is optional — skip it if you only want the warp.
- Send the final IMAGE into `Video Combine` (set your fps, e.g. 24) to export.

> Tip: keep both clips the same fps. If they differ in size, B is auto-resized
> to A. The transition uses the **last N frames of A** and the **first N frames
> of B**, where N = `transition_frames`.

## WarpWiggle Transition — parameters
| param | what it does |
|---|---|
| `transition_frames` | length of the overlap/warp (frames) |
| `warp_pattern` | `horizontal_bands` (smear), `vertical_bands`, `blocks` (mosaic/stair-step), `radial`, `slit_scan` |
| `warp_strength` | how far pixels get pushed (fraction of frame) |
| `warp_frequency` | how many bands/waves across the frame |
| `wiggle_amplitude` / `wiggle_frequency` | the oscillating wobble on top of the warp |
| `wiggle_axis` | horizontal / vertical / both |
| `block_size` | block size for `blocks` pattern + noise granularity (px) |
| `noise_amount` | organic perlin-style melt on top of the sine warp |
| `sweep_direction` | how the A→B wipe travels: top/bottom/left/right/center_out/random_blocks |
| `sweep_softness` | width of the blend seam |
| `easing` | timing curve of the wipe (ease_in_out / linear / snap / …) |
| `edge_mode` | what shows where pixels push out of frame: `zeros` = black borders (reference look), `border`, `reflection` |
| `chromatic_aberration` | RGB split during the warp (0 = off) |
| `parallax` | how differently A and B move (0 = lockstep) |
| `seed` | randomizes the noise/block fields |

### Starting presets
**Reference "TimeSlice" smear** (legible incoming clip):
`warp_pattern=horizontal_bands, warp_strength=0.14, warp_frequency=6,
wiggle_amplitude=0.04, noise_amount=0.15, sweep_direction=top_to_bottom,
sweep_softness=0.2, chromatic_aberration=0.12, edge_mode=zeros`

**Heavy glitch melt:** raise `noise_amount` (0.4+), `warp_strength` (0.25+),
`chromatic_aberration` (0.35), `warp_pattern=blocks`.

## WarpWiggle Stylize (single clip)
One clip in, the warp/wiggle applied continuously to **every frame** (output
length = input length). No second clip, no transition — just the TimeSlice look
as a constant stylization. Chain HUD Overlay after it for the full effect.
```
VHS Load Video ──► WarpWiggle Stylize ──► HUD Overlay ──► VHS Video Combine
```
Defaults are deliberately **subtle** so footage stays legible — push the sliders
for a heavier melt. Key extra controls vs. the transition node:
| param | what it does |
|---|---|
| `motion_speed` | how fast the warp animates over time (0 = frozen distortion) |
| `intensity_mode` | `constant` (steady) or `pulse` (breathes calm→warp→calm) |
| `pulse_count` | number of warp pulses across the whole clip (pulse mode) |
| `pulse_depth` | how far it calms down between pulses (1 = back to clean) |
| `edge_mode` | `reflection` default here (cleaner than black borders for a full-frame effect) |

Same `warp_pattern`, `warp_strength`, `warp_frequency`, `wiggle_*`, `block_size`,
`noise_amount`, `chromatic_aberration`, `seed` as the transition node — but
scaled gentler, since it hits every frame. Tip: keep `warp_strength` ≤ 0.12 and
`noise_amount` ≤ 0.15 unless you want full liquid melt.

## HUD Overlay — parameters
`color_scheme` (rgb_glitch / red / green / mono), `opacity`, `crosshair_count`,
`bar_count`, `corner_brackets`, `scanlines`, `glitch_text` + `text`,
`jitter` (per-frame position shake), `flicker` (random hide), `line_width`, `seed`.

Apply it **after** the transition (or over any clip) for the targeting-HUD look.
```
WarpWiggle Transition ──► HUD Overlay ──► Video Combine
```
