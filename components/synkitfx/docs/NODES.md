# MSCH Synkit FX: node reference

Animated metaball halftones and feature-tracking HUD boxes with labels, connectors, native VIDEO and overlay masks.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## SynkitMetablob

**Display name:** SynkitFX Metablob  
**Category:** `SynkitFX`  
**Output node:** no

Build a square or hexagonal grid whose dot sizes respond to luminance, saturation or edges, then merge neighboring dots into metaball shapes. Threshold, radius, merge and softness tune the field. Pulse, breathing, drift and flicker animate it over a still or frame batch. Outputs VIDEO, processed IMAGE frames and overlay MASK.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `image` | IMAGE | — |  |  |
| `frames` | INT | 48 | 1 to 4096; step 1 | Frames to render from a still. Ignored when the input is already a video batch. |
| `fps` | FLOAT | 24.0 | 1.0 to 120.0; step 1.0 |  |
| `cell_size` | INT | 14 | 3 to 128; step 1 | Grid spacing in pixels. Smaller = more dots. |
| `drive` | COMBO | dark | dark, bright, saturation, edges | What makes a dot grow: dark areas, bright areas, colour saturation or edges. |
| `threshold` | FLOAT | 0.35 | 0.0 to 1.0; step 0.01 | Input values below this produce no dot. Raise to keep only strong areas. |
| `dot_size` | FLOAT | 1.0 | 0.1 to 4.0; step 0.05 | Dot radius multiplier relative to the cell size. |
| `merge` | FLOAT | 0.5 | 0.0 to 1.0; step 0.01 | 0 = clean separated dots, 1 = dots melt into big blobs. |
| `contrast` | FLOAT | 1.5 | 0.2 to 5.0; step 0.05 | Gamma on the drive signal. Higher = only the strongest areas get dots. |
| `softness` | FLOAT | 0.5 | 0.0 to 3.0; step 0.05 | Edge anti-aliasing in pixels. |
| `color` | STRING | #C6FF00 |  | Blob colour as hex. |
| `opacity` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `background` | COMBO | original | original, black, white, transparent_black | What the blobs are drawn on. 'transparent_black' = blobs on black, use the MASK output for alpha. |
| `grid` | COMBO | square | square, hex |  |
| `animate` | COMBO | breathe+drift | off, pulse, breathe, drift, pulse+drift, breathe+drift, flicker | pulse = all dots grow/shrink together. breathe = every dot on its own rhythm. drift = grid slides. flicker = random dots pop in and out. |
| `anim_speed` | FLOAT | 1.0 | 0.0 to 10.0; step 0.05 | Cycles per second. |
| `anim_amount` | FLOAT | 0.35 | 0.0 to 1.0; step 0.01 |  |
| `seed` | INT | 0 | 0 to 4294967295 |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `mask` | MASK | — |  |  |

### Outputs

| Socket | Type |
|---|---|
| `video` | `VIDEO` |
| `frames` | `IMAGE` |
| `blob_mask` | `MASK` |

## SynkitTracker

**Display name:** SynkitFX Tracker  
**Category:** `SynkitFX`  
**Output node:** no

Detect graphic feature points and place animated boxes, corner brackets, labels and connecting wires over the image. Control point count, separation, box sizes, palette and label style; hopping, jitter, flicker and rewiring change the overlay over time. These are visual feature tracks, not recognized objects. Outputs VIDEO, IMAGE frames and an overlay MASK.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `image` | IMAGE | — |  |  |
| `frames` | INT | 48 | 1 to 4096; step 1 | Frames to render from a still. Ignored when the input is already a video batch. |
| `fps` | FLOAT | 24.0 | 1.0 to 120.0; step 1.0 |  |
| `count` | INT | 12 | 1 to 200; step 1 | Number of tracker boxes. |
| `detector` | COMBO | corners | corners, random, grid_jitter | corners = lock onto real image features. random = anywhere. |
| `min_distance` | INT | 60 | 4 to 1000; step 1 | Minimum pixel distance between boxes. |
| `box_min` | INT | 40 | 4 to 2000; step 1 |  |
| `box_max` | INT | 140 | 4 to 4000; step 1 |  |
| `bracket_length` | FLOAT | 0.3 | 0.05 to 0.5; step 0.01 | Corner bracket length as a fraction of the box side. 0.5 = full box. |
| `line_width` | INT | 1 | 1 to 8 |  |
| `color_mode` | COMBO | palette | single, palette, random_hue |  |
| `color` | STRING | #C6FF00 |  |  |
| `palette` | COMBO | neon | neon, pastel, cmyk, rgb, mono_white |  |
| `show_labels` | BOOLEAN | True |  |  |
| `label_style` | COMBO | index+coords | index+coords, coords, index, hex |  |
| `font_scale` | FLOAT | 1.0 | 0.3 to 4.0; step 0.05 |  |
| `crosshairs` | FLOAT | 0.4 | 0.0 to 1.0; step 0.05 | Fraction of boxes that also get a small '+' marker. |
| `connections` | INT | 8 | 0 to 400; step 1 | Number of thin wires drawn between boxes. |
| `connect_mode` | COMBO | random | nearest, random, chain |  |
| `opacity` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `background` | COMBO | original | original, black, transparent_black |  |
| `animate` | COMBO | hop+jitter | off, hop, hop+jitter, wander, wander+jitter, jitter, track, track+jitter | hop = boxes jump to new features every 'hop_every' frames (works on stills). wander = boxes glide around. jitter = per-frame twitch. track = follow real footage with optical flow (video input only). |
| `hop_every` | INT | 12 | 1 to 600; step 1 | Frames between hops. Each box has its own offset so they don't all jump at once. |
| `jitter` | FLOAT | 2.0 | 0.0 to 50.0; step 0.5 | Pixels of per-frame twitch when jitter is on. |
| `flicker` | FLOAT | 0.1 | 0.0 to 1.0; step 0.01 | Probability a box is hidden on a given frame. |
| `rewire_every` | INT | 6 | 0 to 600; step 1 | Frames between re-rolling the wires. 0 = wires stay fixed. |
| `seed` | INT | 0 | 0 to 4294967295 |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `mask` | MASK | — |  |  |

### Outputs

| Socket | Type |
|---|---|
| `video` | `VIDEO` |
| `frames` | `IMAGE` |
| `overlay_mask` | `MASK` |
