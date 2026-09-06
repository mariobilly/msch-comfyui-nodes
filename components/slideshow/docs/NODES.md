# MSCH Slideshow: node reference

Photo slideshow studio with animated layouts, beat analysis, subject framing, editable shot plans and streamed video export.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## marioslideshow

**Display name:** marioslideshow  
**Category:** `marioslideshow`  
**Output node:** yes

Render a complete photo promo from an uploaded photo collection, folder or IMAGE batch. Controls choose timing, scene layouts, framing, transition style, graphics, headlines and quality. Optional audio supplies the soundtrack. Frames stream to a unique output video instead of accumulating the entire movie in RAM. The studio can edit source choices and presentation settings.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `image_folder` | STRING |  |  | Leave empty when photos or images is connected. |
| `width` | INT | 1280 | 64 to 4096; step 2 |  |
| `height` | INT | 720 | 64 to 4096; step 2 |  |
| `fps` | INT | 30 | 1 to 60 |  |
| `timing` | COMBO | BPM | BPM, Seconds |  |
| `bpm` | FLOAT | 128.0 | 20 to 300; step 1 |  |
| `beats_per_image` | FLOAT | 4.0 | 1 to 16; step 0.5 |  |
| `seconds_per_image` | FLOAT | 2.0 | 0.4 to 30; step 0.1 |  |
| `pacing` | COMBO | Dynamic | Dynamic, Even | Dynamic alternates full and half-length shots; minimum 0.4 seconds. |
| `layout` | COMBO | Art directed mix | Art directed mix, Full frame, Layered, Split screen |  |
| `framing` | COMBO | Smart fit | Smart fit, Fill, Contain | Smart fit preserves photos when their aspect ratio differs strongly from the scene. |
| `transition` | COMBO | Mixed | Mixed, Whip, Zoom, Diagonal, Shutter, Impact, Cut |  |
| `transition_seconds` | FLOAT | 0.28 | 0 to 1; step 0.01 |  |
| `intensity` | FLOAT | 0.75 | 0 to 1; step 0.05 |  |
| `motion_blur` | COMBO | Standard (3 samples) | Standard (3 samples), Off, Fine (5 samples) |  |
| `grain` | FLOAT | 0.08 | 0 to 1; step 0.01 |  |
| `accent` | STRING | #DFFF40 |  |  |
| `graphics` | BOOLEAN | True |  |  |
| `headlines` | STRING |  |  | One headline per image; blank lines leave that shot untitled. Multiline text is supported. |
| `font_path` | STRING |  |  | Optional .ttf or .otf file. |
| `audio_file` | STRING |  |  | Optional local soundtrack; alternatively connect AUDIO. |
| `quality` | COMBO | High | High, Preview, Master |  |
| `shuffle` | BOOLEAN | False |  |  |
| `seed` | INT | 0 | 0 to 2147483647 |  |
| `filename_prefix` | STRING | marioslideshow |  |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `photos` | MARIO_IMAGES | — |  |  |
| `images` | IMAGE | — |  |  |
| `audio` | AUDIO | — |  |  |
| `beats` | MARIO_BEATS | — |  |  |
| `focus` | MARIO_FOCUS | — |  |  |
| `show_counter` | BOOLEAN | True |  |  |
| `show_progress` | BOOLEAN | True |  |  |
| `show_headlines` | BOOLEAN | True |  |  |
| `headline_layers` | STRING |  |  | Use Edit headlines. Nonempty layers replace the automatic per-image headlines. Times are seconds from video start. Multiline text is supported. |

### Outputs

| Socket | Type |
|---|---|
| `video` | `VIDEO` |
| `mp4_path` | `STRING` |
| `poster` | `IMAGE` |
| `fps` | `FLOAT` |
| `frame_count` | `INT` |

ComfyUI supplies hidden inputs: `prompt`, `extra_pnginfo`.

## MarioSlideshowLoadImages

**Display name:** marioslideshow - Load Images  
**Category:** `marioslideshow`  
**Output node:** no

Load or upload an ordered photo collection while preserving each image's original aspect ratio. A file limit bounds the collection and Natural/Newest first controls ordering. The collection feeds the slideshow renderer and subject framer; the reported image count feeds the Director.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `directory` | STRING |  |  | Absolute folder path, or a path inside ComfyUI/input. |
| `max_images` | INT | 100 | 1 to 200 |  |
| `order` | COMBO | Natural | Natural, Newest first |  |

### Outputs

| Socket | Type |
|---|---|
| `photos` | `MARIO_IMAGES` |
| `contact_sheet` | `IMAGE` |
| `image_count` | `INT` |

## MarioSlideshowFrames

**Display name:** marioslideshow - Extract Frames  
**Category:** `marioslideshow`  
**Output node:** no

Extract a bounded range from the original Slideshow VIDEO output as an IMAGE batch. start_frame and max_frames select the range; memory_limit_gb rejects a range that would exceed the requested allocation. Outputs the extracted frames and FPS for image effects or VideoHelperSuite. Trimmed or unrelated VIDEO implementations should use native Get Video Components instead.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `video` | VIDEO | — |  |  |
| `start_frame` | INT | 0 | 0 to 1000000 |  |
| `max_frames` | INT | 120 | 1 to 10000 |  |
| `memory_limit_gb` | FLOAT | 1.0 | 0.1 to 32; step 0.1 |  |

### Outputs

| Socket | Type |
|---|---|
| `frames` | `IMAGE` |
| `fps` | `FLOAT` |

## MarioBeatAnalyzer

**Display name:** marioslideshow - Beat Analyzer  
**Category:** `marioslideshow/advanced`  
**Output node:** no

Analyze a supplied soundtrack for musical beat times, with optional tempo hint and timing offset. max_seconds bounds the analyzed window. The beat data feeds the Director; connect the same soundtrack separately to the renderer for audible output. Inspect detected timing because beat detection can choose half/double tempo or miss events.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `audio_file` | STRING |  |  | Leave empty when AUDIO is connected. |
| `tempo_hint` | FLOAT | 0.0 | 0 to 300; step 1 | 0 estimates tempo. Set BPM to correct half/double-tempo detection. |
| `beat_offset_seconds` | FLOAT | 0.0 | -1 to 1; step 0.01 |  |
| `max_seconds` | FLOAT | 180.0 | 2 to 600; step 1 |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `audio` | AUDIO | — |  |  |

### Outputs

| Socket | Type |
|---|---|
| `beats` | `MARIO_BEATS` |
| `bpm` | `FLOAT` |
| `beat_preview` | `IMAGE` |
| `beat_json` | `STRING` |

## MarioSubjectFramer

**Display name:** marioslideshow - Subject Framer  
**Category:** `marioslideshow/advanced`  
**Output node:** no

Compute framing guidance for the source photos using detected faces, masks or a manually chosen focal point. Subject margin controls breathing room; overrides_json supplies explicit per-image corrections. Feed its focus output and the same photo collection into the renderer. It plans crops rather than generating new image content.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `mode` | COMBO | Faces | Faces, Manual |  |
| `subject_margin` | FLOAT | 0.2 | 0 to 1; step 0.05 |  |
| `focus_x` | FLOAT | 0.5 | 0 to 1; step 0.01 |  |
| `focus_y` | FLOAT | 0.5 | 0 to 1; step 0.01 |  |
| `overrides_json` | STRING |  |  | Optional zero-based image overrides, e.g. {"0": {"x": 0.8, "y": 0.3}}. Coordinates are normalized. Multiline text is supported. |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `photos` | MARIO_IMAGES | — |  |  |
| `images` | IMAGE | — |  |  |
| `masks` | MASK | — |  |  |

### Outputs

| Socket | Type |
|---|---|
| `focus` | `MARIO_FOCUS` |
| `framing_preview` | `IMAGE` |
| `focus_json` | `STRING` |

## MarioSlideshowDirector

**Display name:** marioslideshow - Director  
**Category:** `marioslideshow/advanced`  
**Output node:** no

Plan photo order, shot durations, scenes, transitions and headlines without rendering frames. Presets provide a starting style; beat data or manual timing determine pacing. A saved timeline can override automatic planning. Outputs an editable MARIO_PLAN, JSON representation, visual planning chart and total duration for review before rendering.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `image_count` | INT | 8 | 1 to 200 |  |
| `preset` | COMBO | High energy | High energy, Luxury editorial, Cinematic gallery, Hard-cut promo |  |
| `timing` | COMBO | BPM | BPM, Seconds |  |
| `bpm` | FLOAT | 128.0 | 20 to 300; step 1 |  |
| `beats_per_image` | FLOAT | 4.0 | 1 to 16; step 0.5 |  |
| `seconds_per_image` | FLOAT | 2.0 | 0.4 to 30; step 0.1 |  |
| `pacing` | COMBO | Dynamic | Dynamic, Even |  |
| `headlines` | STRING |  |  |  Multiline text is supported. |
| `shuffle` | BOOLEAN | False |  |  |
| `seed` | INT | 0 | 0 to 2147483647 |  |
| `timeline_json_in` | STRING |  |  | Paste edited timeline_json here. It replaces the generated plan, including timing and headlines. Multiline text is supported. |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `beats` | MARIO_BEATS | — |  |  |

### Outputs

| Socket | Type |
|---|---|
| `plan` | `MARIO_PLAN` |
| `timeline_json` | `STRING` |
| `timeline_preview` | `IMAGE` |
| `duration_seconds` | `FLOAT` |

## MarioSlideshowRenderer

**Display name:** marioslideshow - Renderer  
**Category:** `marioslideshow/advanced`  
**Output node:** yes

Render an existing MARIO_PLAN using the source photos, optional framing guidance and soundtrack. Resolution, FPS, transition duration, motion blur, grain and graphics affect final presentation. Reuse the Director's source order and photo collection so indices refer to the intended images. Streams the result to disk through the same engine as the one-node slideshow.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `plan` | MARIO_PLAN | — |  |  |
| `image_folder` | STRING |  |  | Leave empty when photos or images is connected. |
| `width` | INT | 1280 | 64 to 4096; step 2 |  |
| `height` | INT | 720 | 64 to 4096; step 2 |  |
| `fps` | INT | 30 | 1 to 60 |  |
| `framing` | COMBO | Smart fit | Smart fit, Fill, Contain | Smart fit preserves photos when their aspect ratio differs strongly from the scene. |
| `transition_seconds` | FLOAT | 0.28 | 0 to 1; step 0.01 |  |
| `intensity` | FLOAT | 0.75 | 0 to 1; step 0.05 |  |
| `motion_blur` | COMBO | Standard (3 samples) | Standard (3 samples), Off, Fine (5 samples) |  |
| `grain` | FLOAT | 0.08 | 0 to 1; step 0.01 |  |
| `accent` | STRING | #DFFF40 |  |  |
| `graphics` | BOOLEAN | True |  |  |
| `font_path` | STRING |  |  | Optional .ttf or .otf file. |
| `audio_file` | STRING |  |  | Optional local soundtrack; alternatively connect AUDIO. |
| `quality` | COMBO | High | High, Preview, Master |  |
| `seed` | INT | 0 | 0 to 2147483647 |  |
| `filename_prefix` | STRING | marioslideshow |  |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `photos` | MARIO_IMAGES | — |  |  |
| `images` | IMAGE | — |  |  |
| `audio` | AUDIO | — |  |  |
| `focus` | MARIO_FOCUS | — |  |  |
| `show_counter` | BOOLEAN | True |  |  |
| `show_progress` | BOOLEAN | True |  |  |
| `show_headlines` | BOOLEAN | True |  |  |
| `headline_layers` | STRING |  |  | Use Edit headlines. Nonempty layers replace the automatic per-image headlines. Times are seconds from video start. Multiline text is supported. |

### Outputs

| Socket | Type |
|---|---|
| `video` | `VIDEO` |
| `mp4_path` | `STRING` |
| `poster` | `IMAGE` |
| `fps` | `FLOAT` |
| `frame_count` | `INT` |

ComfyUI supplies hidden inputs: `prompt`, `extra_pnginfo`.
