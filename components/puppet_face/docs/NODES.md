# MSCH Puppet Face: node reference

Face landmark and animated cursor overlays with self-contained OpenCV video loading and MP4 saving.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## PuppetFaceOverlay

**Display name:** PuppetFace ▸ Landmark + Cursor Overlay  
**Category:** `PuppetFace`  
**Output node:** no

Draw facial landmark dots, optional connecting mesh and an animated mouse cursor over each frame. Available tracking backends are selected automatically, with a face-box approximation when precise landmarks are unavailable. The cursor can follow a landmark or sweep between normalized coordinates. Dot and mesh settings control appearance; this node overlays existing expressions and does not animate the person's face.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `show_dots` | BOOLEAN | True |  |  |
| `dot_set` | COMBO | key | key, contours, tesselation, all |  |
| `dot_radius` | INT | 2 | 1 to 20 |  |
| `dot_color` | STRING | #FFFFFF |  |  |
| `dot_opacity` | FLOAT | 0.85 | 0.0 to 1.0; step 0.05 |  |
| `show_mesh` | BOOLEAN | False |  |  |
| `mesh_opacity` | FLOAT | 0.25 | 0.0 to 1.0; step 0.05 |  |
| `cursor_mode` | COMBO | track_landmark | track_landmark, sweep, off |  |
| `cursor_scale` | FLOAT | 1.6 | 0.3 to 8.0; step 0.1 |  |
| `cursor_landmark` | INT | 14 | 0 to 477 |  |
| `grab_ring` | BOOLEAN | True |  |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `cursor_target` | COMBO | nose | nose, mouth, eye_left, eye_right, chin, landmark_index |  |
| `sweep_start_x` | FLOAT | 0.15 | 0.0 to 1.0; step 0.01 |  |
| `sweep_start_y` | FLOAT | 0.85 | 0.0 to 1.0; step 0.01 |  |
| `sweep_end_x` | FLOAT | 0.5 | 0.0 to 1.0; step 0.01 |  |
| `sweep_end_y` | FLOAT | 0.55 | 0.0 to 1.0; step 0.01 |  |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |

## PuppetFaceLoadVideo

**Display name:** PuppetFace ▸ Load Video  
**Category:** `PuppetFace`  
**Output node:** no

Decode a selected video into RGB IMAGE frames using OpenCV. Limit the number of frames, sample every nth frame and optionally reduce the maximum image side to bound memory. Outputs the decoded batch, effective FPS after subsampling and frame count. Audio is not decoded.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `video` | COMBO | Select your input clip | Available video files in ComfyUI/input |  |
| `frame_load_cap` | INT | 0 | 0 to 100000 |  |
| `select_every_nth` | INT | 1 | 1 to 100 |  |
| `max_side` | INT | 0 | 0 to 4096 | 0 = keep original; else resize longest side |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `path_override` | STRING |  |  | Full path to ANY video; if set, overrides the dropdown. |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |
| `fps` | `FLOAT` |
| `frame_count` | `INT` |

## PuppetFaceSaveVideo

**Display name:** PuppetFace ▸ Save Video  
**Category:** `PuppetFace`  
**Output node:** yes

Encode an IMAGE batch as a uniquely numbered MP4 in ComfyUI's output directory using OpenCV's mp4v writer. Connect the loader's effective FPS to preserve playback speed. Returns the saved path as STRING and shows the filename in the node UI. It does not mux audio.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `images` | IMAGE | — |  |  |
| `fps` | FLOAT | 24.0 | 1.0 to 120.0 |  Connect this value through an input socket. |
| `filename_prefix` | STRING | PuppetFace |  |  |

### Outputs

| Socket | Type |
|---|---|
| `video_path` | `STRING` |
