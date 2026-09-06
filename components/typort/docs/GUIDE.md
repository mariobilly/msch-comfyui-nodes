> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# mariotyport

A standalone ComfyUI typography studio. No marioslideshow dependency or subscription. Rendering and audio analysis are local. Optional instrument analysis uses an explicitly installed offline Demucs model.

## Start

1. Add **mariotyport** (category: mariotyport) and click **Open typography studio**.
2. Enter your text. Select Tajawal Black, ExtraBold, Bold, Medium, Regular, Light or ExtraLight.
3. Drag the text in the canvas, or enter exact X/Y coordinates. Use **Fit canvas** for oversized titles. Disable Auto fit for intentional cropped typography.
4. Add layers, style them and choose an animation. Drag timeline clips to move them; drag their ends to trim. Entrance/Exit set animation speed independently of the clip's duration.
5. Choose an export format, click **Apply timeline**, then run the ComfyUI node.

**Apply timeline commits edits. Cancel discards them.** The saved project is embedded in the ComfyUI workflow. A nonempty `project_json` overrides the node's text/font/animation/duration defaults. **Reset to node text** explicitly discards that custom timeline. Output resolution, FPS and format remain node settings and can also be changed in the studio.

## Studio

- Up to 60 independent text layers; source-order layering with Forward/Backward, visibility, duplication and deletion.
- Fill, opacity, outline, text block, padding, shadow color/opacity/softness/X/Y, alignment, line height and tracking.
- Layout box size, auto fit, text size, position, scale, rotation and anchor point. Geometry uses percentages of the canvas; size/outline/shadow values use the shorter canvas dimension.
- **Line reveal:** clipped, staggered lines. **Word cascade:** staggered words for Latin; shaped-line staggering for Arabic. **Scale impact:** large-to-settled entry. **Editorial drift:** slow camera-like travel. **Side sweep / Rise:** directional entrances. **Tracking reveal:** expanding Latin spacing. **Fade / Static:** restrained or unanimated text.
- Every animated treatment has entrance, exit, stagger where applicable, travel distance where applicable, and easing. Entrance/exit are capped at 45% of the layer duration to avoid overlapping phases. Stagger is compressed to fit the entrance.
- Linear, Smooth, Power out, or Custom cubic Bezier easing. Drag the two points on the Custom curve, or enter exact coordinates.
- Keyframes store position, scale, rotation and opacity at absolute timeline times. Select a keyframe to edit its values. With keyframes present, canvas dragging inserts/updates a keyframe at the playhead; without them it changes the layer's base position. The first and last keys hold outside their range. Moving clips also moves their keys; trimming drops keys outside the clip.
- Timeline zoom, frame snapping, manual markers, detected audio beats and a manual BPM override/grid. Markers guide editing; per-layer audio reactions are enabled separately.

## Soundtrack And Audio Reactions

1. In the studio's **Soundtrack** section, click **Upload audio**, then **Analyze audio**. WAV, MP3 and other browser/FFmpeg-supported formats can be used. Analysis covers the first 600 seconds at most.
2. The waveform and detected beat markers appear on the timeline. Analysis is saved in the project, so reopening a workflow restores the waveform without another analysis.
3. Drag the audio clip to move it; drag its edges to trim it. **In/Out** are source-file seconds; **Start** is the placement on the typography timeline. Gain and Mute export affect sound, not the reaction strength.
4. Select a text layer and open **Audio reaction**. Pick a trigger, source, sensitivity, threshold, attack and decay. Outline pulse, scale, X/Y travel, opacity dip and shadow softness have independent maximum amounts. The outline uses the existing Outline color control.
5. Apply the timeline and run. The preview and exported frames use the same analyzed signal and timing.

**Triggers:** Beats pulses on detected musical beats (or the BPM override). Hits follows detected transient onsets in the selected source. Energy follows that source's smoothed loudness. For instrument-specific accents, choose **Hits + Drums/Bass/Vocals**. In Beats mode, the grid remains musical beats and a non-Mix source gates pulse strength using its energy. Every N events and Event phase select subdivisions; they do not automatically reschedule headline clips. Attack 0 peaks on the event; a nonzero attack delays the peak by that amount. Decay controls exponential release. Opacity dip darkens/fades the layer between pulses; the other amounts add motion or styling to its base values.

**Sources:** Mix + frequency bands is fast and uses no model. Low band (<180 Hz), Mid band (180-2500 Hz) and High band (>2500 Hz) are frequency ranges, NOT isolated instruments. Select **Separate instruments**, choose a device, and Analyze audio to add Demucs estimates for Drums, Bass, Vocals and Other accompaniment. It takes longer and separation is approximate; guitar, piano and individual drum types are not separately identified. The original soundtrack remains the audible mix.

**Tempo correction:** BPM override 0 uses detected beat times; enter 20-300 for a corrected regular grid. Beat shift adjusts markers/reactions without moving the soundtrack. Use detected markers replaces the snapping markers. Beats can be missed or detected at half/double tempo, so audition the result and correct the grid where needed. There is no automatic downbeat or song-section classifier.

The standalone soundtrack replaces footage audio. It is trimmed, delayed and gain-adjusted identically in preview/export. Source material shorter than the timeline is padded with silence, not looped. Transparent MOV includes the soundtrack while preserving alpha; PNG sequences include a synchronized `soundtrack.wav` sidecar. The checkerboard preview MP4 also carries the audio. A changed audio file fingerprint is rejected until you analyze it again.

### Audio-Synced Text Cues

1. Upload and analyze a soundtrack, then open **Text cues** in the left panel.
2. Choose **Beats**, or **Hits** with an analyzed source such as Drums or Vocals. Set the event interval (for example, every 4 beats) and minimum duration.
3. Click **Generate text cues**. Dashed boxes appear below the waveform, aligned to audio events and rounded to output frames.
4. Set **On cue click** to **New text layer** or **Time selected layer**, then click a box. Enter your headline in the text field. New layers inherit the selected layer's styling; retiming existing text preserves its wording and rescales its keyframe times.
5. Drag or trim the resulting text clip normally. Use **Apply timeline** to save.

Unused cue boxes are editor-only: they never appear in the exported video. Show cue boxes toggles their visibility; Clear unused cues does not delete text. Cue generation replaces unused suggestions, never existing layers. Existing full-length layers remain visible until you hide or retime them, so use Time selected layer for the initial headline when appropriate.

Cues honor the soundtrack's source trim, timeline placement and corrected beat grid. Changing audio timing, replacing audio or reanalyzing clears unused cues; generate them again afterward. Text layers already placed are left unchanged. Undo restores both cue and layer edits. Up to 500 suggestions and 60 actual text layers are supported.

These are musical timing suggestions, not speech transcription or word-aligned subtitles. Vocal hits are detected vocal onsets, not recognized words. Very short intervals are merged or omitted according to minimum duration.

### Optional Instrument Setup

Install using ComfyUI's Python without replacing its torch/torchaudio:

```powershell
E:\ComfyUI_windows_portable\python_embeded\python.exe -m pip install --no-deps -r E:\ComfyUI_windows_portable\ComfyUI\custom_nodes\mariotyport\requirements-stems.txt
E:\ComfyUI_windows_portable\python_embeded\python.exe E:\ComfyUI_windows_portable\ComfyUI\custom_nodes\mariotyport\tests\setup_stems.py --models E:\ComfyUI_windows_portable\ComfyUI\models\mariotyport
```

The second command explicitly downloads the official approximately 80 MB HTDemucs model. Runtime analysis accepts only the verified model and never initiates a download.

For instrument separation, choose **Auto**, **GPU (CUDA)** or **CPU**. Auto uses CUDA when available, otherwise CPU. The completed analysis shows which device was used. GPU runs the Demucs model on audio chunks while the full track and stitched results stay in system RAM. BPM detection, waveform generation and onset extraction remain CPU operations. No PyTorch replacement or additional model is required.

GPU separation shares VRAM with other ComfyUI work. If it runs out of memory, finish other GPU jobs or choose CPU and retry; Auto does not silently restart a failed GPU job on CPU. CPU remains available to avoid GPU contention. The studio accepts one analysis at a time; closing the editor does not cancel an already running backend analysis.

## Arabic

Chromium shapes the original Unicode text using the supplied Tajawal fonts. Direction can be automatic, LTR or RTL. Arabic is never animated as disconnected glyphs: Word cascade becomes line staggering, and tracking changes are disabled for lines containing Arabic/Hebrew. Mixed-language text remains browser-shaped. Use explicit line breaks and preview your exact wording.

## Footage

Upload a video in the studio, then enable Footage reference. A browser-compatible H.264 MP4 is the most predictable preview source. The canvas center-crops footage to match the output aspect ratio. Video offset selects the starting time. Footage holds on its last frame when shorter than the typography timeline.

MP4 composite includes the footage and re-encodes its source audio as AAC unless a standalone soundtrack replaces it. Without footage it uses the chosen solid background. Transparent MOV and PNG sequence export **only the typography image**, even if footage is visible as an editing reference; a standalone soundtrack is supported as described above. Their player preview uses a checkerboard; that checkerboard is not baked into the alpha files.

An absolute `video_file` path can render without upload, but it cannot be previewed directly by the browser. Upload it in the studio for interactive preview. Unsupported browser codecs may still decode for export through FFmpeg/PyAV.

## Export

| Format | Result |
| --- | --- |
| Transparent MOV | ProRes 4444 with alpha; suitable for compositing in an NLE |
| PNG sequence | Numbered, straight-alpha RGBA PNGs starting at 000000; import at the chosen FPS |
| MP4 composite | H.264 with a solid background or uploaded video; no alpha |

Default canvas is 1920x1080, 30 FPS. 3840x2160 is available. Custom even dimensions from 64 to 4096 and 1-60 FPS are accepted. Timeline duration: 0.1-600 seconds. Export duration is rounded up to a whole frame. Text is rasterized at final output resolution; motion blur samples the same engine used by the studio. Preview resolution is capped at 1280 pixels wide, so export edges are sharper at 1080p/4K. This is an SDR, 8-bit canvas renderer; ProRes storage does not turn it into an HDR/true 10-bit source renderer.

Exports go to `ComfyUI/output/mariotyport/<unique-job>/`. Each job includes an editable project manifest, alpha still, poster and playable preview. The node returns the export path, poster IMAGE, alpha MASK (white = opaque), and project JSON. It streams frames rather than accumulating an entire video in RAM. Long 4K ProRes and PNG jobs can consume substantial disk space.

## Installation

Copy this folder to `ComfyUI/custom_nodes/mariotyport`. Install with **ComfyUI's Python**:

```powershell
E:\ComfyUI_windows_portable\python_embeded\python.exe -m pip install -r E:\ComfyUI_windows_portable\ComfyUI\custom_nodes\mariotyport\requirements.txt
E:\ComfyUI_windows_portable\python_embeded\python.exe -m playwright install chromium
```

Restart ComfyUI and hard-refresh the browser. No other custom pack is required. `web/fonts/` contains the seven font files supplied for this installation. Preserve their applicable font license when redistributing; do not assume the project code grants rights to fonts. Lucide icons are bundled under their included license.

## Current Scope

This is a focused 2D motion-typography editor, not a Premiere/After Effects replacement. There is no 3D extrusion, per-character Arabic deformation, arbitrary compositing graph, or multi-track footage editor. Preview and export share timing, shaping and drawing code; playback on a slow machine may drop preview frames. Export renders every frame.

Tests cover schema validation, distinct treatments, Arabic shaping/tracking protection, alpha MOV and PNG decoding, 4K export, footage/audio compositing, cancellation cleanup, and the actual ComfyUI editor workflow.
