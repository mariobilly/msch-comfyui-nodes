> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# ComfyUI-PuppetFace

Recreates the viral **"point and click"** AI-face puppet look: a tracking
landmark mesh + an animated mouse cursor composited over a batch of face
frames — the signature you see in @ingi.ai / @thesystms style reels.

## Where it fits
```
GPT Image 2.0 (portrait)
  → LivePortrait / Wan 2.2  (generate expression frames: snarl, scream, pout, tongue…)
  → [ PuppetFace ▸ Landmark + Cursor Overlay ]   ← this node (the look)
  → Video Combine  (final reel)
```

## The node: `PuppetFace ▸ Landmark + Cursor Overlay`
**Input:** `IMAGE` (a batch of frames). **Output:** `IMAGE` (same batch, overlaid).

Key controls:
- **show_dots / dot_set / dot_radius / dot_color / dot_opacity** — the landmark mesh dots (`key`, `contours`, `tesselation`, `all`).
- **show_mesh / mesh_opacity** — connect the dots with faint mesh lines.
- **cursor_mode** —
  - `track_landmark`: cursor sticks to one landmark every frame (looks like it's *dragging* that feature — e.g. set `cursor_landmark` to a lip point to "pull the tongue").
  - `sweep`: cursor glides from `sweep_start_*` to `sweep_end_*` across the batch.
  - `off`.
- **cursor_scale / grab_ring** — cursor size + a "holding" ring at the tip.

## Landmark tracking — three tiers
1. **cv2 Haar (built in, zero install, ACTIVE NOW):** detects the face box per
   frame and snaps the dot-mesh + cursor onto it. Excellent on frontal frames;
   *approximate* on extreme expressions (screaming/tilted/tongue-out) because
   frontal Haar misses those — it then falls back to a centered rig.
2. **mediapipe FaceMesh (478 pts):** the node auto-uses it *if it imports*, but
   ⚠️ **do not install mediapipe into this portable** — on py3.12 it forces a
   protobuf upgrade that breaks `open-clip-torch`/CLIP. (Tested + reverted
   2026-06-08.)
3. **ONNX 106-pt tracker (RECOMMENDED upgrade):** true per-expression tracking
   via `onnxruntime` (already installed, no protobuf conflict). Needs a ~5 MB
   model download. This is the next build step — ask Claude to wire it.

`cursor_landmark` index (used in track_landmark mode when real landmarks exist):
- mediapipe: lower-lip `14`, upper-lip `13`, mouth corners `61`/`291`, nose tip `1`, chin `152`.
- In Haar fallback the cursor auto-anchors to the mouth region (index ignored).

## Tip for the trend look
720×720 or 1080×1080, floating head on a flat gray gradient, then run the
expression frames (LivePortrait poses or Wan 2.2 i2v) through this node with
`cursor_mode=track_landmark` on a lip point and `dot_set=key`.
