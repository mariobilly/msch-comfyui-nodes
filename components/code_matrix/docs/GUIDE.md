> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# ComfyUI-CodeMatrix

A custom node that turns a video into **green "code" art** on black — each frame
rebuilt from monospace glyphs whose brightness/density follows the image (the
classic ASCII-portrait / Matrix look).

IMAGE in / IMAGE out, so it drops into a VideoHelperSuite workflow:
```
VHS Load Video ──► Code Matrix (ASCII) ──► VHS Video Combine
```

## Install
Folder lives in `ComfyUI/custom_nodes/ComfyUI-CodeMatrix`. **Fully restart
ComfyUI**, then find **Code Matrix (ASCII)** under the **CodeMatrix** category.
No pip installs — uses torch + numpy + Pillow (all bundled with ComfyUI).

## Three looks
- **ASCII portrait** (default, matches a detailed reference): `char_set=ascii_dense`,
  `char_pick=by_brightness` — glyphs chosen by brightness, full ramp.
- **Binary 0/1**: `char_set=binary`, `char_pick=random` — only 0s and 1s, the
  figure emerges from where characters appear (above `threshold`).
- **Matrix code-rain**: `char_set=matrix`, `char_pick=random`, raise `flicker`
  for shimmering characters that change each frame.

## Parameters
| param | what it does |
|---|---|
| `char_set` | ascii_dense / ascii_simple / binary / matrix / custom |
| `char_pick` | `by_brightness` (glyph = brightness, portrait look) or `random` (random glyphs, gated by threshold — code-rain look) |
| `custom_chars` | your own character set (used when char_set=custom); order dark→light for by_brightness |
| `columns` | how many characters across — higher = finer detail, smaller glyphs |
| `color_mode` | green / amber / cyan / white / custom / **original** (keep the video's colors) |
| `custom_color` / `background` | hex colors, e.g. `#33FF66` / `#000000` |
| `gamma`, `contrast` | tune how brightness maps to glyph density |
| `invert` | swap dark/light |
| `threshold` | (random mode) cells darker than this stay blank — controls how much of the frame fills |
| `flicker` | (random mode) fraction of glyphs that re-randomize each frame (code-rain shimmer) |
| `bold` | thicker glyphs |
| `seed` | randomization for random mode |

### Tips
- Want the exact reference portrait? `ascii_dense` + `by_brightness`, `columns`
  120–180, `contrast` ~1.3, `color_mode=green`.
- True "binary numbers": `binary` + `random`, `threshold` ~0.14.
- Performance: glyphs are rendered once into an atlas and placed vectorized, so
  long clips are fast. Higher `columns` = more cells = a bit slower.
