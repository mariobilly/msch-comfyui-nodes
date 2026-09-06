# MSCH Code Matrix: node reference

Convert images and video frames into ASCII portraits, binary art and animated Matrix-style glyph patterns.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## CodeMatrixASCII

**Display name:** Code Matrix (ASCII)  
**Category:** `CodeMatrix`  
**Output node:** no

Rebuild each input frame from a monospace glyph atlas. Brightness mode selects glyphs from a dark-to-light ramp; random mode distributes characters above a luminance threshold and can refresh them over time. Choose ASCII, binary, Matrix or a custom character set, then set column density, colors and tonal mapping. Returns the rendered IMAGE batch for further processing or video encoding.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `char_set` | COMBO | ascii_dense | ascii_dense, ascii_simple, binary, matrix, custom |  |
| `char_pick` | COMBO | by_brightness | by_brightness, random |  |
| `custom_chars` | STRING | 01 |  |  |
| `columns` | INT | 140 | 16 to 600 |  |
| `color_mode` | COMBO | green | green, amber, cyan, white, custom, original |  |
| `custom_color` | STRING | #33FF66 |  |  |
| `background` | STRING | #000000 |  |  |
| `gamma` | FLOAT | 1.0 | 0.2 to 4.0; step 0.05 |  |
| `contrast` | FLOAT | 1.0 | 0.2 to 3.0; step 0.05 |  |
| `invert` | BOOLEAN | False |  |  |
| `threshold` | FLOAT | 0.12 | 0.0 to 1.0; step 0.01 |  |
| `flicker` | FLOAT | 0.0 | 0.0 to 1.0; step 0.05 |  |
| `bold` | BOOLEAN | False |  |  |
| `seed` | INT | 0 | 0 to 4294967295 |  |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |
