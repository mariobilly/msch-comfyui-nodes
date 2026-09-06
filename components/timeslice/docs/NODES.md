# MSCH TimeSlice: node reference

Temporal displacement of video bands and cubes with time-offset color ramps, RGB spread and jitter.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## TimeSlice

**Display name:** TimeSlice ▸ Temporal Displacement  
**Category:** `TimeSlice`  
**Output node:** no

Sample different input-frame times at different spatial positions. Vertical or horizontal bands receive offsets controlled by span_frames, band_px, anchor and curve. Optional cubic blocks extend the time field into two dimensions. Edge mode resolves out-of-range times; pixelation, seeded jitter, channel time spread and tint add stylization. A still image or zero time span passes through unchanged.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `axis` | COMBO | vertical | vertical, horizontal |  |
| `span_frames` | INT | 16 | 0 to 240 | Frames of time spread across the frame. Bigger = more smear. |
| `band_px` | INT | 1 | 1 to 256 | 1 = smooth slit-scan; larger = chunky constant-time bands. |
| `anchor` | FLOAT | 0.5 | 0.0 to 1.0; step 0.05 | Where the zero-time line sits (0=top, .5=middle, 1=bottom). |
| `curve` | COMBO | linear | linear, ease |  |
| `edge` | COMBO | clamp | clamp, wrap, mirror |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `pixelate_px` | INT | 0 | 0 to 64 | 0=off. Downsample each band into NxN blocks (datamosh). |
| `jitter_px` | INT | 0 | 0 to 200 | Max random sideways shift per band (deterministic by seed). |
| `jitter_seed` | INT | 0 | 0 to 2147483647 |  |
| `chroma_spread` | INT | 0 | 0 to 60 | Per-RGB-channel time offset. >0 = colorful chromatic fringing along the slice. |
| `cubic_px` | INT | 0 | 0 to 256 | 0=off (flat bands). >0 = 2D TIME-CUBES of this size; time flows in both axes. |
| `cubic_lateral` | FLOAT | 1.0 | 0.0 to 3.0; step 0.1 | How much time also flows sideways across cubes (cubic mode only). |
| `tint_mode` | COMBO | off | off, rainbow, thermal, ice, neon |  |
| `tint_strength` | FLOAT | 0.0 | 0.0 to 1.0; step 0.05 | Blend a color ramp keyed to each band/cube's time-offset. |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |
