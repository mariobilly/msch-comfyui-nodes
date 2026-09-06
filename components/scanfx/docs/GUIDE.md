> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# ComfyUI-ScanFX

One node — **Scan FX** — that turns a single image or a video (frame batch) into a
sci-fi "scan" look, confined to an optional mask. Stack and mix up to 8 effects.

## Node
`ScanFX` → shows up as **Scan FX (thermal / nightvision / hud / ...)** under the
**ScanFX** category (right-click → Add Node → ScanFX, or double-click search "Scan FX").

### Inputs
- **image** (IMAGE) — 1 image, or a video as a frame batch (e.g. from *VHS Load Video*).
- **mask** (MASK, optional) — effects are composited back onto the original **only inside the mask**. No mask = whole frame.
- **mix** — global opacity of the whole effect stack inside the mask (0–1).
- **mask_feather** — soften the mask edge, in pixels.
- **invert_mask** — flip the mask.
- **animation_speed** — speed of moving effects (holo sweep, sonar, ekg, code-rain, hud, glitch). On a single image these are static; on video they move per frame.
- **seed** — randomization for glitch / code-rain / lidar / noise.
- **effect_1 … effect_8** + **strength_1 … strength_8** — the stack. Each slot picks one effect (or `none`) and its strength (0–1). **Slots apply in order**, so order = layering order. Pick the same effect twice for a stronger pass.

### Output
- **image** (IMAGE) — same shape as input (passes straight into *VHS Video Combine* for video).

## The 15 effects
`thermal` (FLIR ironbow) · `falsecolor` (IR false-color, non-thermal) · `nightvision`
(green phosphor) · `xray` · `depthmap` (grayscale*) · `lidar` (point cloud) ·
`wireframe` (mesh overlay) · `holo_sweep` (scan-line sweep) · `hologram` (volumetric
flicker) · `chroma` (chromatic aberration edges) · `glitch` (datamosh) · `hud`
(targeting reticle) · `sonar` (radar pulse) · `ekg` (waveform pulse) · `coderain`
(terminal / matrix overlay).

\* No depth model is bundled — `depthmap` approximates depth from luminance. For a true
depth map, feed a Depth-Anything output into `image` and skip this effect (you already
have ComfyUI-DepthAnythingV3 installed).

## Typical graph
**Image:** Load Image → Scan FX → Preview/Save Image.
**Video:** VHS Load Video → Scan FX → VHS Video Combine.
**Masked:** any mask source (SAM / CLIPSeg / Load Image Mask) → Scan FX `mask`.

## Tips
- Mix realistic looks: e.g. `thermal` (1.0) + `hud` (0.6) + `chroma` (0.3).
- `hologram` = `holo_sweep` + chroma + scanlines + flicker in one slot.
- Heavy overlays (`hud`, `sonar`, `ekg`, `coderain`) need OpenCV (already installed here).

Restart ComfyUI (or use Manager → Restart) after installing so the node loads.
