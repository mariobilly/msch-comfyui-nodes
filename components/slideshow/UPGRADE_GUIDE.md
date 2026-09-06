# marioslideshow: Modular Upgrade

Your original marioslideshow node stays available. The advanced workflow separates analysis, shot planning and rendering, so you can adjust one stage without rebuilding everything.

## Quick Start

1. Restart ComfyUI after installing the upgrade, then hard-refresh the browser (Ctrl+F5).
2. Drag `examples/modular_high_energy.json` onto the canvas.
3. Click **Upload images** on Load Images and choose your photos.
4. Choose the Director preset and enter one headline per source image, or leave headlines empty.
5. Set Renderer resolution and quality, then Run.

The basic modular workflow is already wired:

```text
Load Images.photos ------> Subject Framer.photos
Load Images.photos ------> Renderer.photos
Load Images.image_count -> Director.image_count
Subject Framer.focus ----> Renderer.focus
Director.plan ----------> Renderer.plan
```

Output files go to `ComfyUI/output/marioslideshow`: MP4, poster and a JSON manifest containing settings, the shot plan and framing data. Preview and download the video directly in Renderer. Native VIDEO output works with ComfyUI video nodes; Extract Frames remains available when an IMAGE batch is needed.

## Music-Driven Workflow

Load `examples/modular_music.json`. Upload/select your soundtrack in the standard Load Audio node. Its AUDIO output is connected to BOTH Beat Analyzer and Renderer; the analyzer does not forward the soundtrack. Beat Analyzer.beats connects to Director.beats.

Alternatively, enter the same local audio path in Beat Analyzer.audio_file and Renderer.audio_file. Leave those fields empty when AUDIO is connected. Use only one audio source per node.

- **tempo_hint**: 0 estimates BPM. Enter the known BPM if detection locks to half or double tempo.
- **beat_offset_seconds**: shifts the detected markers, not the audio. Positive values delay shot boundaries.
- **max_seconds**: analyze up to this much audio, default 180, maximum 600 seconds.
- **beats_per_image**: use a whole number with detected beats. Four is a practical starting point.
- **Dynamic** creates a seeded opening/build/contrast/closing rhythm. Energetic presets mix shorter runs with longer holds; calm presets favor longer holds. This is procedural pacing, not automatic song-section detection. **Even** advances the same number of markers for each shot.

Connected beats override the Director's manual BPM/Seconds timing controls. Video begins at zero; subsequent shot boundaries follow detected markers and are rounded to output frames. The first shot includes the track's initial offset. Transitions begin at those boundaries, not at their midpoint. The final shot ends on a selected marker.

If there are too few markers, reduce beats per image or image count, analyze more of the track, or disconnect beats and use manual timing. Silence is rejected. Beat detection is an estimate, particularly with ambient music, weak percussion or changing rhythm; inspect the waveform preview and listen to the render. It does not detect musical sections or drops.

## Subject Framer

Connect the same source images in the same order to Framer and Renderer. Faces mode detects frontal faces using a local classical detector. Green boxes show protected regions; the red cross is the focus point. A center fallback is used when no face is found. The preview shows up to 12 images, but all images are analyzed.

- **subject_margin** expands detected face/mask bounds.
- **Manual** uses normalized focus_x and focus_y, from 0 to 1.
- Optional **masks** must contain one mask per image, in matching order. White (>0.5) means subject, black means background. Masks override face detection. Invert transparency masks when necessary.
- **overrides_json** changes specific zero-based source images. Example: `{"0":{"x":0.8,"y":0.3}}` focuses the first source toward its upper-right region.
- An override can also include `"box":[0.6,0.1,0.95,0.7]`, ordered left, top, right, bottom in normalized coordinates.

Smart fit can switch to a contained photo if the protected region will not fit the crop. Fill may still crop a subject that is wider/taller than the output aspect ratio allows. Framing guides camera movement within photo panels; it is not foreground segmentation and cannot prevent all transition occlusion or overlapping layers. Faces mode is not a universal object detector. Use masks or manual focus for products and difficult portraits.

## Director

The Director outputs a shot plan, readable JSON, a timeline preview and total duration. It does not render the video.

| Preset | Shot Arrangement |
| --- | --- |
| High energy | Full-frame, asymmetric split, stack, triptych and mosaic; strong pushes, pulls, pans and snap settles |
| Luxury editorial | Light gallery mattes, full-frame and split compositions; restrained camera travel, cuts, dissolves and diagonal reveals |
| Cinematic gallery | Dark gallery/window framing and full-frame shots; gentle camera travel, dissolves and cuts |
| Hard-cut promo | Full-frame and multi-panel compositions; holds, snap settles and pans with direct cuts only |

Presets now control composition, camera path, motion strength and Dynamic pacing. Seed changes the arrangement without changing image order unless shuffle is enabled. Short fixed layout loops have been replaced with seeded selection that discourages recent repeats. Renderer intensity multiplies the preset's motion strength; graphics, grain and motion blur remain independent. Subject protection can reduce motion to keep a face or mask visible.

Headlines follow source images when shuffled. Seed makes order deterministic. The connected image_count keeps the plan matched to the collection. Without beats, use BPM or Seconds timing as on the original node.

### Edit Individual Shots

Run once, then click **Edit generated plan**. The generated JSON appears in timeline_json_in. Change shot order, duration, scene, incoming transition, headline or image_index, then run again. You may repeat a source image or remove shots. Image indices start at zero.

```json
{
  "version": 1,
  "source_count": 2,
  "shots": [
    {"image_index": 0, "duration": 1.5, "scene": "hero", "transition": "cut", "headline": "MARIO"},
    {"image_index": 1, "duration": 0.8, "scene": "split", "transition": "whip", "headline": "IN MOTION"}
  ]
}
```

source_count must match the loaded collection, even if some images are unused. Supported scenes: hero, split, triptych, stack, gallery, window, mosaic. Supported transitions: cut, whip, zoom, diagonal, shutter, impact, dissolve. Optional shot fields: motion (push, pull, left, right, rise, snap, hold), strength (0-1), variant (integer 0-7). Older plans without these fields retain their original camera behavior. Durations: 0.4 to 120 seconds per shot. Maximum: 200 shots and 200 source images. Headlines: at most 240 characters per shot.

**Nonempty timeline_json_in replaces all generated timing, ordering, preset and headline choices, including connected beats. Click Use preset / clear custom plan to return to automatic planning.** Changing the preset while a custom plan is active displays a warning; it does not discard your edits. Editing JSON does not automatically preserve beat alignment. Multi-panel scenes use following source images for their secondary panels.

## Renderer and Original Node

### Counters and Free-Position Headlines

These controls are on both the original node and the advanced Renderer:

- **show_counter = false** hides the current-shot / total-shot numbers in the corner.
- **show_progress = false** hides the line along the bottom.
- **show_headlines = false** hides all text headlines without deleting them.
- **graphics** remains the master switch for counters, progress and accent graphics; it does not hide headline text.

Click **Edit headlines**, then **Add headline**. Drag text on the placement canvas, or enter X/Y percentages. X/Y specify the top-left of its text box; Width sets the box width. Size is a percentage of the shorter video dimension. Alignment places text within the box. Long text automatically wraps/shrinks to fit the remaining frame area.

Start and End are seconds from the beginning of the whole video, not from a particular image. For example, two headlines with start=2/end=4 appear together between seconds 2 and 4. Change the second start to 3 for a staggered entrance. A headline can span several shots; it does not move with a shuffled source photo. Times outside the video will not be visible.

Use the time slider to inspect active text layers. Select a layer in the list to jump to its time. Each layer supports color, left/center/right alignment, fade/slide/none animation and a Visible checkbox. Add up to 200 layers; Duplicate copies the selected one, Delete removes it. Later layers paint over earlier layers. Apply saves changes; Close or Escape cancels them.

The optional background is a still poster from the last render, not the current image at the slider time. Browser typography is approximate, especially with a custom font_path; the exported video is the final reference. Render once to obtain a poster, then position text and render again.

A nonempty **headline_layers** list replaces the Director/original node's automatic headlines. Delete every custom layer and Apply to restore automatic headlines. Existing workflows retain their original behavior and need no rewiring. After installing, restart ComfyUI and hard-refresh to load the new controls.

Renderer takes plan plus photos or IMAGE, and optional focus/audio. It shares the original engine, streaming MP4 export, aspect ratios, captions, grain, quality modes and motion blur. Start at 1280x720 with Standard blur; use 1920x1080 for final delivery. Rendering is CPU-based. Master is high-quality H.264, not lossless or an editable After Effects project.

For a simpler upgrade, keep your original marioslideshow node and connect Beat Analyzer.beats to its new beats input and/or Subject Framer.focus to its focus input. Existing required settings and outputs are unchanged. The Director plan connects to the new Renderer, not to the original node.

## Dependencies and Troubleshooting

With Windows portable, run from the portable root:

```powershell
python_embeded\python.exe -m pip install -r ComfyUI\custom_nodes\marioslideshow\requirements.txt
python_embeded\python.exe -m pip install -r ComfyUI\custom_nodes\marioslideshow\requirements-advanced.txt
```

Advanced analysis uses librosa and scikit-image; no paid service or model download is needed. The original renderer can load without these optional packages. PyTorch and PyAV come from ComfyUI.

- Red/UNKNOWN nodes: restart the ComfyUI process and hard-refresh the browser; check startup logs for import errors.
- Missing faces: inspect fallback labels, add manual overrides or supply masks.
- Mismatched focus/plan counts: use the same collection for Framer, Director count and Renderer.
- Changing preset does nothing: clear timeline_json_in.
- No soundtrack: connect AUDIO to Renderer as well as Analyzer, or enter the renderer audio_file.
- Slow render: preview at lower resolution with motion blur Off, then restore final settings.

This upgrade does not add generative video, automatic cutouts, 3D depth, musical-section detection or After Effects project export.
