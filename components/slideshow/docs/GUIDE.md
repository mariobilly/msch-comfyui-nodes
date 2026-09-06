> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# marioslideshow

A local ComfyUI node pack for high-energy photo promos. No diffusion model, Adobe subscription, or cloud service is needed.

## Start

1. Put this folder in `ComfyUI/custom_nodes/marioslideshow`.
2. Install `requirements.txt` with the Python that runs ComfyUI. On Windows portable:
   `python_embeded\python.exe -m pip install -r ComfyUI\custom_nodes\marioslideshow\requirements.txt`
3. Restart ComfyUI and refresh the browser. Search for **marioslideshow**.
4. Click **Upload images** on the main node, select multiple photos, then queue it. Alternatively enter an image folder or connect an IMAGE batch.

The ready-to-load workflow is `examples/high_energy.json`. Drop it onto the ComfyUI canvas, upload photos in its Load Images node, and run.

MP4, poster and render-settings JSON files are saved under `ComfyUI/output/marioslideshow`. The node includes a video player and download link. Its native VIDEO output connects to **Save Video**, **Get Video Components**, and other standard video nodes.

## Animation

- Full-frame hero shots, asymmetric split screens, three-panel scenes, and rotating layered photo compositions.
- Whip, zoom, diagonal, staggered shutter, and restrained impact transitions.
- Subpixel eased camera movement and temporal supersampling for motion blur.
- Animated headlines, adjustable accent color, optional shot counters and progress line, subtle grain.
- Landscape, square and portrait rendering. Portrait split screens use horizontal bands. Smart fit preserves mixed-aspect photos against a softened backdrop; Fill and Contain are also available.
- BPM grid or seconds-based pacing. Dynamic pacing alternates full and half-length shots, with a minimum of 0.4 seconds. Even pacing keeps every image the same length.
- Optional soundtrack from a local file or an AUDIO connection. Short audio is padded with silence; long audio is trimmed to the video.
- Deterministic shuffle and transition variation using the seed.

## Controls

The default is 1280x720 at 30 fps, 128 BPM, four beats per image, dynamic pacing, mixed layouts, and three motion-blur samples. Use 1920x1080 for landscape delivery, 1080x1920 for vertical, or 1080x1080 for square. **Master** increases H.264 quality; it is not a lossless export. **Preview** uses faster encoding.

Headlines use one line per image, with blank lines allowed. They follow their image when shuffled. Use a TTF/OTF font path to choose your own font. Long captions are fitted into the frame. Turn off **graphics** for photos and optional headlines without counters or accent lines.

Both the original node and Renderer now have independent **show_counter**, **show_progress**, and **show_headlines** switches. Keep graphics on and turn off show_counter/show_progress to remove the numbers and bottom line while retaining accent styling.

Click **Edit headlines** for up to 200 independently timed text layers. Add, duplicate or delete headlines; drag them into position or enter X/Y percentages. Each has its own start/end time in seconds, width, size, color, alignment, fade/slide/no animation, and visibility. Click Apply to store them in the workflow. Custom layers replace automatic per-image headlines; delete all layers to return to that mode. The placement preview uses browser typography and an optional last-render poster, not a live preview of each shot. Export uses font_path and fits text within the frame.

**Load Images** preserves the original aspect ratio of mixed-size photos and outputs a contact sheet. It reads up to 200 files in natural filename order or newest-first order. Folder loading is non-recursive. Photos are decoded on demand during rendering.

**Extract Frames** converts a selected range of the original marioslideshow VIDEO output into an IMAGE batch for VideoHelperSuite. It checks the requested float32 batch size against a memory limit before allocating. Native **Get Video Components** can extract the whole video, but a long 1080p batch can require many GB of RAM.

## Limits

This is a procedural 2D compositor with photo layers, not an After Effects project generator. It does not infer subject cutouts, reconstruct 3D depth, or choose compositions with an AI model. Without optional analysis inputs, BPM is manual and Fill uses center cropping. Rendering runs on the CPU and streams frames to FFmpeg, so export memory does not grow with video length. Higher resolution and five-sample motion blur take longer.

Supported input formats: PNG, JPEG, WebP, BMP and TIFF. Requires a current ComfyUI with the native VIDEO API, Pillow 10.1+, NumPy, and FFmpeg with libx264. PyTorch and PyAV are supplied by ComfyUI. If FFmpeg is not on PATH, `imageio-ffmpeg` supplies a bundled executable.

## Modular Upgrade

The original node and workflow remain available. Four additional nodes live under `marioslideshow/advanced`:

- **Beat Analyzer** detects soundtrack beat timestamps, with an optional tempo hint and offset.
- **Subject Framer** uses faces, supplied subject masks, or manual focus coordinates to guide cropping and camera movement.
- **Director** creates editable shot plans with High energy, Luxury editorial, Cinematic gallery and Hard-cut promo presets.
- **Renderer** exports a Director plan using the same motion-graphics engine and video preview.

Install `requirements-advanced.txt` with ComfyUI's Python for beat detection and face detection. No model download is required. The original node also accepts optional `beats` and `focus` inputs.

Load `examples/modular_high_energy.json` for the four-node photo workflow, or `examples/modular_music.json` for the music-driven workflow. See [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md) for wiring, editable timeline examples, and limitations. The PDF guide includes the upgrade too.

## Development

`python -m unittest discover -s tests -v` checks timing, transitions, framing, deterministic rendering, audio duration, and MP4 encoding. `python demo.py --images /path/to/photos --output ./demo` renders a local sample and contact sheet.

The node follows the [ComfyUI custom-node interface](https://docs.comfy.org/custom-nodes/backend/server_overview) and its [IMAGE batch contract](https://docs.comfy.org/custom-nodes/backend/datatypes).
