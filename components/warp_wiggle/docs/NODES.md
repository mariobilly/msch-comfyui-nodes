# MSCH Warp Wiggle: node reference

Warped transitions between video clips, animated single-clip distortion and matching HUD overlays.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## WarpWiggleTransition

**Display name:** WarpWiggle Transition  
**Category:** `WarpWiggle`  
**Output node:** no

Join two IMAGE clips through an overlapping spatial warp and moving blend seam. The last transition_frames of A meet the first transition_frames of B; B is resized to A's dimensions. Band, block, radial and slit-scan patterns shape displacement, while wiggle, noise, parallax and RGB separation add movement. The returned frame count is len(A) + len(B) minus the effective overlap.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images_a` | IMAGE | — |  |  |
| `images_b` | IMAGE | — |  |  |
| `transition_frames` | INT | 16 | 2 to 600 |  |
| `warp_pattern` | COMBO | horizontal_bands | horizontal_bands, vertical_bands, blocks, radial, slit_scan |  |
| `warp_strength` | FLOAT | 0.18 | 0.0 to 1.0; step 0.01 |  |
| `warp_frequency` | FLOAT | 5.0 | 0.5 to 60.0; step 0.5 |  |
| `wiggle_amplitude` | FLOAT | 0.05 | 0.0 to 0.5; step 0.01 |  |
| `wiggle_frequency` | FLOAT | 7.0 | 0.5 to 60.0; step 0.5 |  |
| `wiggle_axis` | COMBO | both | horizontal, vertical, both |  |
| `block_size` | INT | 48 | 4 to 512 |  |
| `noise_amount` | FLOAT | 0.35 | 0.0 to 1.0; step 0.01 |  |
| `sweep_direction` | COMBO | top_to_bottom | top_to_bottom, bottom_to_top, left_to_right, right_to_left, center_out, random_blocks |  |
| `sweep_softness` | FLOAT | 0.22 | 0.01 to 1.0; step 0.01 |  |
| `easing` | COMBO | ease_in_out | ease_in_out, linear, ease_in, ease_out, snap |  |
| `edge_mode` | COMBO | zeros | zeros, border, reflection |  |
| `chromatic_aberration` | FLOAT | 0.3 | 0.0 to 1.0; step 0.01 |  |
| `parallax` | FLOAT | 0.5 | -1.0 to 1.0; step 0.05 |  |
| `seed` | INT | 0 | 0 to 4294967295 |  |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |

## WarpWiggleStylize

**Display name:** WarpWiggle Stylize (1 clip)  
**Category:** `WarpWiggle`  
**Output node:** no

Apply animated distortion to one IMAGE clip without joining another clip. Spatial pattern and warp frequency define the displacement field. Motion speed advances it through the batch, while constant or pulsed intensity controls when it peaks. The output remains an IMAGE batch with matching timing for an external encoder.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `warp_pattern` | COMBO | horizontal_bands | horizontal_bands, vertical_bands, blocks, radial, slit_scan |  |
| `warp_strength` | FLOAT | 0.05 | 0.0 to 1.0; step 0.01 |  |
| `warp_frequency` | FLOAT | 4.0 | 0.5 to 60.0; step 0.5 |  |
| `wiggle_amplitude` | FLOAT | 0.02 | 0.0 to 1.0; step 0.01 |  |
| `wiggle_frequency` | FLOAT | 6.0 | 0.5 to 60.0; step 0.5 |  |
| `wiggle_axis` | COMBO | both | horizontal, vertical, both |  |
| `block_size` | INT | 48 | 4 to 512 |  |
| `noise_amount` | FLOAT | 0.05 | 0.0 to 1.0; step 0.01 |  |
| `motion_speed` | FLOAT | 0.15 | 0.0 to 2.0; step 0.01 |  |
| `intensity_mode` | COMBO | constant | constant, pulse |  |
| `pulse_count` | FLOAT | 4.0 | 0.1 to 60.0; step 0.1 |  |
| `pulse_depth` | FLOAT | 0.7 | 0.0 to 1.0; step 0.05 |  |
| `chromatic_aberration` | FLOAT | 0.06 | 0.0 to 1.0; step 0.01 |  |
| `edge_mode` | COMBO | reflection | reflection, border, zeros |  |
| `seed` | INT | 0 | 0 to 4294967295 |  |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |

## HUDOverlay

**Display name:** HUD Overlay  
**Category:** `WarpWiggle`  
**Output node:** no

Composite graphic crosshairs, bars, corner brackets, scanlines and optional glitch text over a frame batch. Select a palette and set opacity, density, line width, jitter and flicker. This is a decorative overlay; it does not detect or track objects.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `color_scheme` | COMBO | rgb_glitch | rgb_glitch, red, green, mono |  |
| `opacity` | FLOAT | 0.9 | 0.0 to 1.0; step 0.05 |  |
| `crosshair_count` | INT | 6 | 0 to 60 |  |
| `bar_count` | INT | 8 | 0 to 80 |  |
| `corner_brackets` | BOOLEAN | True |  |  |
| `scanlines` | BOOLEAN | False |  |  |
| `glitch_text` | BOOLEAN | True |  |  |
| `text` | STRING | REC ● SYS//TIMESLICE |  |  |
| `jitter` | FLOAT | 0.5 | 0.0 to 1.0; step 0.05 |  |
| `flicker` | FLOAT | 0.25 | 0.0 to 1.0; step 0.05 |  |
| `line_width` | INT | 2 | 1 to 8 |  |
| `seed` | INT | 0 | 0 to 4294967295 |  |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |
