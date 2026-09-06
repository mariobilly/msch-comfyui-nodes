> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# ComfyUI-SynkitFX

Two chainable nodes that recreate the Synkit "metablob + tracker" look
(dot/blob halftone plus HUD tracking boxes) inside ComfyUI and output an
animated **VIDEO**. Feed a single still and set `frames`, or feed a video
batch and every frame is processed. CPU only, no models, needs only numpy +
OpenCV (both ship with ComfyUI).

Nodes live under the **SynkitFX** category. Each node outputs:

- `video` (VIDEO) -> plug into **Save Video**
- `frames` (IMAGE batch) -> chain into the next SynkitFX node, or into VHS / Create Video
- a MASK of the overlay

## Workflow

`Load Image` -> `SynkitFX Metablob` (frames out) -> `SynkitFX Tracker` (video out) -> `Save Video`

`example_workflow.json` has this wired up with the settings from the original
post. Drag it onto the canvas. Frame width and height must be even for the
H.264 encoder, so crop or resize odd-sized images first.

## SynkitFX Metablob

A grid of dots whose size follows the image. Dots are merged with a metaball
field so they fuse into solid blobs.

| Setting | What it does |
| --- | --- |
| `frames` / `fps` | Length and rate of the output when the input is a still. |
| `cell_size` | Grid spacing in px. Smaller = more dots. |
| `drive` | What grows a dot: `dark` (shadows), `bright`, `saturation`, `edges`. |
| `threshold` | Cut-off on the drive signal. Raise it to keep only strong areas. |
| `dot_size` | Dot radius relative to the cell. |
| `merge` | 0 = clean dots, 1 = everything melts into blobs. |
| `contrast` | Gamma on the drive signal. |
| `softness` | Edge anti-aliasing. |
| `color` | Hex colour of the blobs. |
| `background` | `original`, `black`, `white`, or `transparent_black` (use the MASK output as alpha). |
| `grid` | `square` or `hex`. |
| `animate` | `pulse` (all dots together), `breathe` (each dot on its own rhythm), `drift` (grid slides), `flicker` (dots pop in/out), or combos. |
| `anim_speed` / `anim_amount` | Cycles per second and strength. |

Recipes from the original post:

- **Dot look (slide 3):** `cell_size 14`, `merge 0`, `threshold 0.35`, colour `#39FF14`.
- **Blob look (slide 4):** `cell_size 12`, `merge 0.8`, `threshold 0.45`, `dot_size 1.3`, `contrast 2`, colour `#C6FF00`.

## SynkitFX Tracker

Corner-bracket tracking boxes with index + pixel-coordinate labels,
crosshairs and thin connecting wires.

| Setting | What it does |
| --- | --- |
| `frames` / `fps` | Length and rate of the output when the input is a still. |
| `count` | Number of boxes. |
| `detector` | `corners` locks onto real image features, `random`, `grid_jitter`. |
| `box_min` / `box_max` | Box size range in px. |
| `bracket_length` | Corner bracket length as a fraction of the side (0.5 = full box). |
| `color_mode` | `single`, `palette` (each box its own colour), `random_hue`. |
| `label_style` | `index+coords`, `coords`, `index`, `hex`. |
| `connections` / `connect_mode` | How many wires and how they are chosen. |
| `animate` | `hop` (boxes jump to new features), `wander` (boxes glide), `jitter` (twitch), `track` (optical flow on real footage), or combos. |
| `hop_every` | Frames between hops. Boxes are staggered so they don't all jump at once. |
| `flicker` | Chance a box is hidden on a frame. |
| `rewire_every` | Frames between re-rolling the wires. 0 = fixed. |

Optional `mask` input on both nodes limits the effect to a region.
