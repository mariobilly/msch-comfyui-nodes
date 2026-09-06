"""
ComfyUI-ScanFX
==============
A single custom node that turns a still image OR a video (a batch of frames)
into a sci-fi "scan" look: thermal/FLIR, night vision, x-ray, LiDAR point cloud,
wireframe, holographic sweep, HUD reticle, sonar/radar, glitch/datamosh,
hologram flicker, EKG waveform, code-rain, chromatic aberration, IR false-color
and depth-map grayscale.

Design:
  * Input is IMAGE (B,H,W,3 float 0..1) -> works for 1 image or N video frames.
  * Optional MASK (B,H,W float 0..1): the whole effect stack is composited back
    onto the original ONLY inside the (feathered) mask. No mask = whole frame.
  * 8 effect "slots". Each slot = a dropdown (which effect) + a strength.
    Slots are applied in order, so you can stack/mix and control the order.
  * Time-based effects (sweeps, sonar, glitch, code-rain, ekg) animate using the
    frame index, so on a video they move; on a single image they are static.

Everything is plain numpy + OpenCV, no models, CPU only.
"""

import numpy as np
import torch

try:
    import cv2
    HAS_CV2 = True
except Exception:
    HAS_CV2 = False


# -----------------------------------------------------------------------------
# small helpers (all operate on float images H,W,3 in 0..1, RGB)
# -----------------------------------------------------------------------------
def _lum(img):
    return img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114


def _clip(x):
    return np.clip(x, 0.0, 1.0)


def _gray3(g):
    return np.repeat(g[..., None], 3, axis=2)


def _blur(img, sigma):
    if sigma <= 0:
        return img
    if HAS_CV2:
        k = max(1, int(sigma * 3) | 1)
        return cv2.GaussianBlur(img, (k, k), sigma)
    # cheap separable box fallback
    r = max(1, int(sigma))
    ker = np.ones(2 * r + 1) / (2 * r + 1)
    out = img.copy()
    for c in range(img.shape[2]):
        out[..., c] = np.apply_along_axis(lambda m: np.convolve(m, ker, mode="same"), 0, out[..., c])
        out[..., c] = np.apply_along_axis(lambda m: np.convolve(m, ker, mode="same"), 1, out[..., c])
    return out


def _edges(gray):
    """Return 0..1 edge magnitude image from a 0..1 gray image."""
    g8 = (_clip(gray) * 255).astype(np.uint8)
    if HAS_CV2:
        e = cv2.Canny(g8, 60, 160).astype(np.float32) / 255.0
        return e
    gx = np.zeros_like(gray); gy = np.zeros_like(gray)
    gx[:, 1:-1] = gray[:, 2:] - gray[:, :-2]
    gy[1:-1, :] = gray[2:, :] - gray[:-2, :]
    m = np.sqrt(gx * gx + gy * gy)
    return _clip(m / (m.max() + 1e-6))


def _lut_from_points(points):
    """points: list of (pos0..1, (r,g,b)0..1). Returns [256,3] LUT."""
    xs = np.array([p[0] for p in points])
    cols = np.array([p[1] for p in points])
    grid = np.linspace(0, 1, 256)
    lut = np.stack([np.interp(grid, xs, cols[:, c]) for c in range(3)], axis=1)
    return lut.astype(np.float32)


def _apply_lut(gray, lut):
    idx = (_clip(gray) * 255).astype(np.uint8)
    return lut[idx]


# classic FLIR "ironbow" palette
IRONBOW = _lut_from_points([
    (0.00, (0.00, 0.00, 0.00)),
    (0.15, (0.15, 0.00, 0.35)),
    (0.35, (0.55, 0.00, 0.55)),
    (0.55, (0.90, 0.20, 0.20)),
    (0.72, (1.00, 0.55, 0.00)),
    (0.88, (1.00, 0.85, 0.20)),
    (1.00, (1.00, 1.00, 0.95)),
])

# infrared false-color (CIR vegetation look: bright magenta/pink + cyan)
CIR = _lut_from_points([
    (0.00, (0.02, 0.02, 0.10)),
    (0.25, (0.10, 0.30, 0.55)),
    (0.50, (0.20, 0.65, 0.55)),
    (0.70, (0.85, 0.35, 0.65)),
    (1.00, (1.00, 0.75, 0.90)),
])


def _vignette(shape, strength=0.6):
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    d /= d.max() + 1e-6
    return _clip(1.0 - strength * (d ** 2))


def _scanlines(h, w, period=3, depth=0.35, offset=0):
    rows = ((np.arange(h) + offset) % period) == 0
    line = np.ones(h, np.float32)
    line[rows] = 1.0 - depth
    return np.repeat(line[:, None], w, axis=1)


# -----------------------------------------------------------------------------
# effects.  signature: fn(img, ctx) -> img   (full-strength result)
# ctx: dict with frame, total, t (animated phase), rng, seed, mask
# slot strength blending is done by the caller.
# -----------------------------------------------------------------------------
def fx_thermal(img, ctx):
    g = _lum(img)
    g = _clip((g - 0.02) / 0.96)
    g = _blur(_gray3(g), 0.6)[..., 0]
    return _apply_lut(g, IRONBOW)


def fx_falsecolor(img, ctx):
    g = _lum(img)
    return _apply_lut(g, CIR)


def fx_nightvision(img, ctx):
    h, w = img.shape[:2]
    g = _lum(img)
    g = _clip(g ** 0.7 * 1.3)
    noise = ctx["rng"].normal(0, 0.06, (h, w)).astype(np.float32)
    g = _clip(g + noise)
    out = np.zeros_like(img)
    out[..., 0] = g * 0.10
    out[..., 1] = g
    out[..., 2] = g * 0.18
    out *= _scanlines(h, w, 3, 0.30, ctx["frame"])[..., None]
    out *= _vignette((h, w), 0.7)[..., None]
    bloom = _blur(out, 3.0) * 0.5
    return _clip(out + bloom)


def fx_xray(img, ctx):
    g = _lum(img)
    inv = 1.0 - g
    inv = _clip((inv - 0.1) * 1.25 + 0.1)
    e = _edges(g)
    base = _gray3(inv)
    tint = np.array([0.80, 0.90, 1.00], np.float32)
    out = base * tint
    out = _clip(out + e[..., None] * np.array([0.4, 0.5, 0.6], np.float32))
    return out


def fx_depthmap(img, ctx):
    # no real depth available -> approximate from luminance + local contrast
    g = _lum(img)
    g = _blur(_gray3(g), 1.5)[..., 0]
    g = _clip((g - g.min()) / (g.max() - g.min() + 1e-6))
    g = g ** 0.8
    return _gray3(g)


def fx_lidar(img, ctx):
    h, w = img.shape[:2]
    g = _lum(img)
    e = _edges(g)
    step = max(3, int(min(h, w) / 140))
    out = np.zeros_like(img)
    ys = np.arange(0, h, step)
    xs = np.arange(0, w, step)
    gy, gx = np.meshgrid(ys, xs, indexing="ij")
    jit = ctx["rng"].integers(-1, 2, gy.shape)
    sy = np.clip(gy + jit, 0, h - 1)
    sx = np.clip(gx + jit, 0, w - 1)
    val = g[sy, sx]
    dense = (e[sy, sx] > 0.1) | (ctx["rng"].random(sy.shape) < 0.5)
    # color points by "distance" (use luminance as proxy): near=cyan, far=blue
    col = np.zeros((*sy.shape, 3), np.float32)
    col[..., 0] = val * 0.2
    col[..., 1] = 0.4 + val * 0.6
    col[..., 2] = 0.7 + val * 0.3
    col *= dense[..., None]
    out[sy, sx] = col
    if HAS_CV2:
        out = cv2.dilate(out, np.ones((2, 2), np.uint8))
    return _clip(out)


def fx_wireframe(img, ctx):
    h, w = img.shape[:2]
    g = _lum(img)
    e = _edges(g)
    if HAS_CV2:
        e = cv2.dilate(e, np.ones((2, 2), np.uint8))
    out = _gray3(g) * 0.12
    wire = np.array([0.1, 1.0, 0.8], np.float32)
    out = _clip(out + e[..., None] * wire)
    # faint mesh grid
    grid = np.zeros((h, w), np.float32)
    gs = max(12, int(min(h, w) / 22))
    grid[::gs, :] = 1.0
    grid[:, ::gs] = 1.0
    out = _clip(out + grid[..., None] * np.array([0.0, 0.18, 0.16], np.float32))
    return out


def fx_holo_sweep(img, ctx):
    h, w = img.shape[:2]
    g = _lum(img)
    out = _gray3(g) * np.array([0.15, 0.85, 1.0], np.float32)
    pos = int((ctx["t"] * 0.5 % 1.0) * h)
    band = np.exp(-((np.arange(h) - pos) ** 2) / (2 * (h * 0.05) ** 2))
    out = _clip(out + band[:, None, None] * np.array([0.3, 0.9, 1.0], np.float32))
    out *= _scanlines(h, w, 2, 0.25, ctx["frame"])[..., None]
    return out


def fx_hologram(img, ctx):
    h, w = img.shape[:2]
    g = _lum(img)
    out = _gray3(g) * np.array([0.25, 0.9, 1.0], np.float32)
    # chroma split
    sh = max(1, int(w * 0.004))
    out[..., 0] = np.roll(out[..., 0], sh, axis=1)
    out[..., 2] = np.roll(out[..., 2], -sh, axis=1)
    out *= _scanlines(h, w, 2, 0.4, ctx["frame"])[..., None]
    flick = 0.85 + 0.15 * np.sin(ctx["t"] * 2.0) + ctx["rng"].normal(0, 0.04)
    out *= flick
    e = _edges(g)
    out = _clip(out + e[..., None] * np.array([0.2, 0.7, 0.9], np.float32))
    out *= _vignette((h, w), 0.5)[..., None]
    return _clip(out)


def fx_chroma(img, ctx):
    h, w = img.shape[:2]
    amt = 0.02
    if HAS_CV2:
        def zoom(ch, scale):
            M = cv2.getRotationMatrix2D((w / 2, h / 2), 0, scale)
            return cv2.warpAffine(ch, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        r = zoom(img[..., 0], 1.0 + amt)
        b = zoom(img[..., 2], 1.0 - amt)
        out = np.stack([r, img[..., 1], b], axis=2)
    else:
        sh = max(1, int(w * amt))
        out = img.copy()
        out[..., 0] = np.roll(img[..., 0], sh, axis=1)
        out[..., 2] = np.roll(img[..., 2], -sh, axis=1)
    return _clip(out)


def fx_glitch(img, ctx):
    h, w = img.shape[:2]
    rng = np.random.default_rng(ctx["seed"] * 9973 + ctx["frame"])
    out = img.copy()
    nbands = rng.integers(3, 10)
    for _ in range(int(nbands)):
        y0 = rng.integers(0, h)
        bh = rng.integers(2, max(3, h // 12))
        y1 = min(h, y0 + bh)
        shift = rng.integers(-w // 12, w // 12)
        out[y0:y1] = np.roll(out[y0:y1], shift, axis=1)
        if rng.random() < 0.5:
            c = rng.integers(0, 3)
            out[y0:y1, :, c] = np.roll(out[y0:y1, :, c], rng.integers(-15, 15), axis=1)
    # global channel split
    s = rng.integers(-6, 7)
    out[..., 0] = np.roll(out[..., 0], s, axis=1)
    out[..., 2] = np.roll(out[..., 2], -s, axis=1)
    if rng.random() < 0.4:  # scanline corruption
        out *= _scanlines(h, w, 2, 0.5, ctx["frame"])[..., None]
    return _clip(out)


def _overlay_init(h, w):
    return np.zeros((h, w, 3), np.float32)


def fx_hud(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    ov = _overlay_init(h, w)
    col = (0.1, 1.0, 0.4)
    cx, cy = w // 2, h // 2
    r = int(min(h, w) * 0.32)
    cv2.circle(ov, (cx, cy), r, col, 1, cv2.LINE_AA)
    cv2.circle(ov, (cx, cy), int(r * 0.6), col, 1, cv2.LINE_AA)
    # rotating ticks
    ang0 = ctx["t"] * 0.4
    for i in range(24):
        a = ang0 + i * np.pi / 12
        x1 = int(cx + np.cos(a) * r); y1 = int(cy + np.sin(a) * r)
        x2 = int(cx + np.cos(a) * (r * (0.9 if i % 3 else 0.82)))
        y2 = int(cy + np.sin(a) * (r * (0.9 if i % 3 else 0.82)))
        cv2.line(ov, (x1, y1), (x2, y2), col, 1, cv2.LINE_AA)
    # crosshair
    g = max(8, r // 6)
    cv2.line(ov, (cx - r, cy), (cx - g, cy), col, 1, cv2.LINE_AA)
    cv2.line(ov, (cx + g, cy), (cx + r, cy), col, 1, cv2.LINE_AA)
    cv2.line(ov, (cx, cy - r), (cx, cy - g), col, 1, cv2.LINE_AA)
    cv2.line(ov, (cx, cy + g), (cx, cy + r), col, 1, cv2.LINE_AA)
    cv2.drawMarker(ov, (cx, cy), col, cv2.MARKER_CROSS, 12, 1, cv2.LINE_AA)
    # corner brackets
    m = int(min(h, w) * 0.06); L = int(min(h, w) * 0.08)
    for (px, py, dx, dy) in [(m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)]:
        cv2.line(ov, (px, py), (px + dx * L, py), col, 1, cv2.LINE_AA)
        cv2.line(ov, (px, py), (px, py + dy * L), col, 1, cv2.LINE_AA)
    ov = (_clip(ov) * 255).astype(np.uint8)
    col = tuple(round(c * 255) for c in col)
    cv2.putText(ov, "TRACKING", (m, m + L + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
    cv2.putText(ov, "LOCK %03d" % (int(ctx["t"] * 7) % 100), (w - m - 120, h - m - L - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
    return _clip(img * 0.85 + ov.astype(np.float32) / 255)


def fx_sonar(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    g = _lum(img)
    base = _gray3(g) * np.array([0.02, 0.18, 0.05], np.float32)
    ov = _overlay_init(h, w)
    col = (0.1, 1.0, 0.3)
    cx, cy = w // 2, h // 2
    R = int(min(h, w) * 0.46)
    for rr in np.linspace(R * 0.25, R, 4):
        cv2.circle(ov, (cx, cy), int(rr), col, 1, cv2.LINE_AA)
    cv2.line(ov, (cx - R, cy), (cx + R, cy), col, 1, cv2.LINE_AA)
    cv2.line(ov, (cx, cy - R), (cx, cy + R), col, 1, cv2.LINE_AA)
    # sweeping arm with fading wedge
    ang = ctx["t"] * 0.8
    for k in range(28):
        a = ang - k * 0.03
        x = int(cx + np.cos(a) * R); y = int(cy + np.sin(a) * R)
        f = (1.0 - k / 28.0)
        cv2.line(ov, (cx, cy), (x, y), tuple(c * f for c in col), 1, cv2.LINE_AA)
    # blips
    rng = np.random.default_rng(ctx["seed"] + 7)
    for _ in range(5):
        a = rng.random() * 2 * np.pi; rad = rng.random() * R
        bx = int(cx + np.cos(a) * rad); by = int(cy + np.sin(a) * rad)
        pulse = 0.5 + 0.5 * np.sin(ctx["t"] * 3 + a * 5)
        cv2.circle(ov, (bx, by), 3, tuple(c * pulse for c in col), -1, cv2.LINE_AA)
    return _clip(base + ov)


def fx_ekg(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    ov = _overlay_init(h, w)
    col = (0.1, 1.0, 0.3)
    # grid
    gs = max(14, h // 20)
    for y in range(0, h, gs):
        cv2.line(ov, (0, y), (w, y), (0.0, 0.12, 0.04), 1)
    for x in range(0, w, gs):
        cv2.line(ov, (x, 0), (x, h), (0.0, 0.12, 0.04), 1)
    # waveform: baseline + QRS spike, scrolling
    midy = int(h * 0.55)
    amp = h * 0.22
    head = int((ctx["t"] * 0.9 % 1.0) * w)
    pts = []
    for x in range(0, w, 2):
        phase = ((x - head) % w) / w  # 0..1 along beat
        beat = np.sin(phase * 2 * np.pi) * 0.08
        # sharp QRS around 0.5
        d = phase - 0.5
        qrs = np.exp(-(d ** 2) / (2 * 0.0008)) * 1.0 - np.exp(-((d - 0.02) ** 2) / (2 * 0.0008)) * 0.5
        y = int(midy - (beat + qrs) * amp)
        pts.append((x, y))
    for i in range(1, len(pts)):
        # fade older (further left of head) part
        cv2.line(ov, pts[i - 1], pts[i], col, 2, cv2.LINE_AA)
    cv2.circle(ov, pts[-1], 3, (0.6, 1.0, 0.7), -1, cv2.LINE_AA)
    ov = (_clip(ov) * 255).astype(np.uint8)
    col = tuple(round(c * 255) for c in col)
    cv2.putText(ov, "BPM %d" % (60 + int(20 * np.sin(ctx["t"]))), (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 1, cv2.LINE_AA)
    return _clip(img * 0.5 + ov.astype(np.float32) / 255)


def fx_coderain(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    g = _lum(img)
    out = (_gray3(g) * np.array([0.0, 0.15, 0.0], np.float32) * 255).astype(np.uint8)
    cw = 12  # column width / glyph size
    cols = w // cw
    rows = h // cw
    rng = np.random.default_rng(ctx["seed"] + 1234)
    speeds = rng.integers(1, 4, cols)
    starts = rng.integers(0, rows, cols)
    chars = "0123456789ABCDEFｱｲｳｴｵｶｷｸ$#%&*+=<>"
    for c in range(cols):
        head = (starts[c] + int(ctx["t"] * speeds[c])) % (rows + 8)
        x = c * cw
        for tlen in range(10):
            ry = head - tlen
            if ry < 0 or ry >= rows:
                continue
            y = ry * cw + cw
            bright = 1.0 - tlen / 10.0
            color = (0.4 * bright, 1.0 * bright, 0.4 * bright) if tlen == 0 else (0.0, 0.85 * bright, 0.15 * bright)
            ch = chars[rng.integers(0, len(chars))]
            color = tuple(round(c * 255) for c in color)
            cv2.putText(out, ch, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    return _clip(out.astype(np.float32) / 255 + _gray3(g) * 0.08)


# -----------------------------------------------------------------------------
# extra helpers for the second effect pack
# -----------------------------------------------------------------------------
def _noise(h, w, rng, cells=8):
    """Smooth value-noise in 0..1 by upscaling a low-res random grid."""
    cells = max(2, int(cells))
    low = rng.random((cells, cells)).astype(np.float32)
    if HAS_CV2:
        return cv2.resize(low, (w, h), interpolation=cv2.INTER_CUBIC)
    ry = h // cells + 1
    rx = w // cells + 1
    return np.kron(low, np.ones((ry, rx), np.float32))[:h, :w]


def _remap(img, mapx, mapy):
    if HAS_CV2:
        return cv2.remap(img, mapx.astype(np.float32), mapy.astype(np.float32),
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    h, w = img.shape[:2]
    xi = np.clip(mapx, 0, w - 1).astype(np.int32)
    yi = np.clip(mapy, 0, h - 1).astype(np.int32)
    return img[yi, xi]


def _motion(img, angle_deg, length):
    length = int(length)
    if length < 2:
        return img
    if HAS_CV2:
        k = np.zeros((length, length), np.float32)
        k[length // 2, :] = 1.0
        M = cv2.getRotationMatrix2D((length / 2, length / 2), angle_deg, 1.0)
        k = cv2.warpAffine(k, M, (length, length))
        s = k.sum()
        k /= s if s > 0 else 1.0
        return cv2.filter2D(img, -1, k)
    return _blur(img, length / 3.0)


# -----------------------------------------------------------------------------
# effect pack 2
# -----------------------------------------------------------------------------
def fx_sketch(img, ctx):
    g = _lum(img)
    inv = 1.0 - g
    b = _blur(_gray3(inv), 3.0)[..., 0]
    dodge = np.minimum(1.0, g / (1.0 - b + 1e-3))
    return _gray3(_clip(dodge))


def fx_blueprint(img, ctx):
    h, w = img.shape[:2]
    g = _lum(img)
    e = _edges(g)
    if HAS_CV2:
        e = cv2.dilate(e, np.ones((2, 2), np.uint8))
    out = np.ones_like(img) * np.array([0.05, 0.15, 0.45], np.float32)
    grid = np.zeros((h, w), np.float32)
    gs = max(16, min(h, w) // 24)
    grid[::gs, :] = 1.0
    grid[:, ::gs] = 1.0
    out = _clip(out + grid[..., None] * 0.10)
    out = _clip(out + e[..., None] * np.array([0.7, 0.85, 1.0], np.float32))
    return out


def fx_halftone(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    g = _lum(img)
    out = np.ones((h, w, 3), np.float32) * 0.96
    cell = max(4, min(h, w) // 90)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            v = g[y:y + cell, x:x + cell].mean()
            r = (1.0 - v) * cell * 0.72
            if r > 0.3:
                cv2.circle(out, (x + cell // 2, y + cell // 2), int(r), (0.05, 0.05, 0.05), -1, cv2.LINE_AA)
    return out


def fx_ascii(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    g = _lum(img)
    chars = " .:-=+*#%@"
    cw = max(6, min(h, w) // 70)
    ch = int(cw * 1.8)
    out = np.zeros((h, w, 3), np.uint8)
    for y in range(0, h, ch):
        for x in range(0, w, cw):
            v = float(g[y:y + ch, x:x + cw].mean())
            c = chars[int(v * (len(chars) - 1))]
            col = 0.25 + 0.75 * v
            cv2.putText(out, c, (x, y + ch - 2), cv2.FONT_HERSHEY_SIMPLEX, cw / 22.0,
                        (26, round(col * 255), 64), 1, cv2.LINE_AA)
    return out.astype(np.float32) / 255


def fx_pixelate(img, ctx):
    h, w = img.shape[:2]
    f = max(4, min(h, w) // 64)
    if HAS_CV2:
        small = cv2.resize(img, (max(1, w // f), max(1, h // f)), interpolation=cv2.INTER_LINEAR)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    return img


def fx_posterize(img, ctx):
    levels = 5
    q = np.round(img * (levels - 1)) / (levels - 1)
    e = _edges(_lum(img))
    return _clip(q * (1.0 - 0.6 * e[..., None]))


def fx_sobel(img, ctx):
    g = _lum(img)
    if HAS_CV2:
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        m = np.sqrt(gx * gx + gy * gy)
    else:
        m = _edges(g)
    return _gray3(_clip(m / (m.max() + 1e-6)))


def fx_bloom(img, ctx):
    h, w = img.shape[:2]
    g = _lum(img)
    hl = _clip((g - 0.6) / 0.4)[..., None] * img
    bloom = _blur(hl, 6.0) * 1.6
    xx = np.linspace(0, 1, w)[None, :]
    leak = (0.5 + 0.5 * np.sin(ctx["t"] * 0.2)) * np.exp(-((xx - 0.85) ** 2) / 0.02)
    leakc = leak[..., None] * np.array([1.0, 0.7, 0.4], np.float32)
    return _clip(img + bloom + leakc * np.ones((h, 1, 1), np.float32) * 0.4)


def fx_lensflare(img, ctx):
    if not HAS_CV2:
        return _clip(img + _blur(img, 4.0) * 0.3)
    h, w = img.shape[:2]
    g = _lum(img)
    ly, lx = np.unravel_index(int(np.argmax(g)), g.shape)
    ov = np.zeros_like(img)
    cv2.line(ov, (0, ly), (w, ly), (0.4, 0.5, 1.0), 2, cv2.LINE_AA)
    ov = _blur(ov, 3.0)
    cx, cy = w / 2.0, h / 2.0
    for tt in (0.0, 0.3, 0.6, 1.0, 1.4):
        px = int(lx + (cx - lx) * tt)
        py = int(ly + (cy - ly) * tt)
        cv2.circle(ov, (px, py), int(8 + 10 * tt), (0.3 * (1 - tt * 0.4), 0.4, 0.6), -1, cv2.LINE_AA)
    ov = _blur(ov, 2.0)
    return _clip(img + ov * 0.8)


def fx_vhs(img, ctx):
    h, w = img.shape[:2]
    out = img.copy()
    sh = max(2, int(w * 0.006))
    out[..., 0] = np.roll(out[..., 0], sh, axis=1)
    out[..., 2] = np.roll(out[..., 2], -sh, axis=1)
    rng = np.random.default_rng(ctx["seed"] + ctx["frame"])
    nl = rng.random(h) < 0.04
    if nl.any():
        out[nl] = _clip(out[nl] + rng.normal(0, 0.25, (int(nl.sum()), w, 3)).astype(np.float32))
    band = int((ctx["t"] * 0.3 % 1.0) * h)
    bh = max(2, h // 40)
    out[band:band + bh] = _clip(out[band:band + bh] * 0.5 + 0.3)
    out = out * _scanlines(h, w, 2, 0.15, ctx["frame"])[..., None]
    return _clip(out + rng.normal(0, 0.04, (h, w, 1)).astype(np.float32))


def fx_crt(img, ctx):
    h, w = img.shape[:2]
    mask = np.ones((h, w, 3), np.float32) * 0.7
    mask[:, 0::3, 0] = 1.0
    mask[:, 1::3, 1] = 1.0
    mask[:, 2::3, 2] = 1.0
    out = img * mask
    out = out * _scanlines(h, w, 2, 0.35, 0)[..., None]
    out = _clip(out + _blur(out, 2.0) * 0.5)
    out = out * _vignette((h, w), 0.5)[..., None]
    return _clip(out * 1.2)


def fx_filmgrain(img, ctx):
    h, w = img.shape[:2]
    rng = np.random.default_rng(ctx["seed"] + ctx["frame"])
    grain = rng.normal(0, 0.07, (h, w, 1)).astype(np.float32)
    out = _clip(img + grain * (0.4 + 0.6 * (1.0 - _lum(img))[..., None]))
    out = out * _vignette((h, w), 0.45)[..., None]
    if rng.random() < 0.5:
        for _ in range(int(rng.integers(2, 8))):
            x = int(rng.integers(0, w)); y = int(rng.integers(0, h)); l = int(rng.integers(2, 10))
            out[y:y + l, x:x + 1] = 1.0
    return _clip(out)


def fx_lightpaint(img, ctx):
    g = _lum(img)
    hl = _clip((g - 0.5) / 0.5)[..., None] * img
    streak = hl.copy()
    for d in (1, 2, 4, 8, 16):
        streak = streak + np.roll(hl, d, axis=1) * (1.0 / d)
    streak = _blur(_clip(streak * 0.5), 2.0)
    return _clip(img + streak)


def fx_motionblur(img, ctx):
    return _motion(img, ctx["t"] * 2.0, max(5, int(img.shape[1] * 0.03)))


def fx_slitscan(img, ctx):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    off = np.sin(yy * 0.05 + ctx["t"] * 0.5) * w * 0.04
    return _remap(img, np.clip(xx + off, 0, w - 1), yy)


def fx_kaleidoscope(img, ctx):
    h, w = img.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = xx - cx; dy = yy - cy
    r = np.sqrt(dx * dx + dy * dy)
    a = np.arctan2(dy, dx)
    seg = 6
    a = np.abs(((a * seg / (2 * np.pi)) % 1.0) - 0.5) * 2.0
    a = a * (2 * np.pi / seg) + ctx["t"] * 0.05
    return _remap(img, np.clip(cx + np.cos(a) * r, 0, w - 1), np.clip(cy + np.sin(a) * r, 0, h - 1))


def fx_fisheye(img, ctx):
    h, w = img.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx - cx) / cx; ny = (yy - cy) / cy
    r = np.sqrt(nx * nx + ny * ny)
    scale = np.where(r > 1e-6, (r * (1 + 0.5 * r * r)) / np.maximum(r, 1e-6), 1.0)
    return _remap(img, np.clip(cx + nx * scale * cx, 0, w - 1), np.clip(cy + ny * scale * cy, 0, h - 1))


def fx_tiltshift(img, ctx):
    h, w = img.shape[:2]
    yy = np.linspace(-1, 1, h)[:, None]
    bm = np.repeat(_clip((np.abs(yy) - 0.2) / 0.5), w, axis=1)[..., None]
    out = img * (1 - bm) + _blur(img, 5.0) * bm
    g = _lum(out)[..., None]
    out = _clip((out - g) * 1.4 + g)
    return _clip((out - 0.5) * 1.15 + 0.5)


def fx_doubleexp(img, ctx):
    flipped = img[:, ::-1, :]
    out = 1.0 - (1.0 - img) * (1.0 - flipped * 0.65)
    return _clip(out * 0.7 + img * 0.3)


def fx_solarize(img, ctx):
    return np.where(img < 0.5, img, 1.0 - img).astype(np.float32)


def fx_duotone(img, ctx):
    g = _lum(img)[..., None]
    shadow = np.array([0.1, 0.05, 0.3], np.float32)
    hi = np.array([1.0, 0.8, 0.2], np.float32)
    return _clip(shadow * (1 - g) + hi * g)


def fx_neon(img, ctx):
    g = _lum(img)
    e = _edges(g)
    if HAS_CV2:
        e = cv2.dilate(e, np.ones((2, 2), np.uint8))
    col = np.array([1.0, 0.1, 0.8], np.float32)
    glow = _blur(e[..., None] * col, 4.0) * 1.8
    return _clip(_gray3(g) * 0.1 + e[..., None] * col + glow)


def fx_heathaze(img, ctx):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    n = _noise(h, w, ctx["rng"], 12)
    dx = (np.sin(yy * 0.1 + ctx["t"] * 0.8) + (n - 0.5) * 2.0) * w * 0.01
    dy = np.cos(xx * 0.08 + ctx["t"] * 0.6) * h * 0.006
    return _remap(img, np.clip(xx + dx, 0, w - 1), np.clip(yy + dy, 0, h - 1))


def fx_dissolve(img, ctx):
    h, w = img.shape[:2]
    n = _noise(h, w, np.random.default_rng(ctx["seed"] + 1), 40)
    thr = (ctx["t"] * 0.05) % 1.0
    xx = np.linspace(0, 1, w)[None, :]
    field = n * 0.6 + xx * 0.4
    keep = (field > thr)[..., None]
    edge = (np.abs(field - thr) < 0.03)[..., None]
    return _clip(img * keep + edge * np.array([1.0, 0.6, 0.2], np.float32))


def fx_voronoi(img, ctx):
    h, w = img.shape[:2]
    rng = np.random.default_rng(ctx["seed"] + 5)
    npts = 80
    px = rng.integers(0, w, npts); py = rng.integers(0, h, npts)
    yy, xx = np.mgrid[0:h, 0:w]
    mind = np.full((h, w), 1e18, np.float32)
    idx = np.zeros((h, w), np.int32)
    for i in range(npts):
        d = (xx - px[i]) ** 2 + (yy - py[i]) ** 2
        m = d < mind
        mind[m] = d[m]; idx[m] = i
    seedcols = img[np.clip(py, 0, h - 1), np.clip(px, 0, w - 1)]
    out = seedcols[idx]
    gx = np.abs(np.diff(idx, axis=1, prepend=idx[:, :1]))
    gy = np.abs(np.diff(idx, axis=0, prepend=idx[:1, :]))
    cracks = ((gx + gy) > 0)[..., None]
    return _clip(out * (1 - cracks))


def fx_spectrum(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    g = _lum(img)
    out = img * 0.3
    nb = 48; bw = max(1, w // nb)
    for i, c in enumerate(np.array_split(g, nb, axis=1)):
        amp = float(c.mean()) * (0.6 + 0.4 * np.sin(ctx["t"] * 0.5 + i * 0.4))
        bh = int(_clip(amp) * h)
        x = i * bw
        cv2.rectangle(out, (x, h - bh), (x + bw - 1, h), (0.1 + 0.9 * i / nb, 1.0 - 0.6 * i / nb, 0.8), -1)
    return _clip(out)


def fx_topographic(img, ctx):
    g = _blur(_gray3(_lum(img)), 1.5)[..., 0]
    levels = 12
    q = np.round(g * levels) / levels
    gx = np.abs(np.diff(q, axis=1, prepend=q[:, :1]))
    gy = np.abs(np.diff(q, axis=0, prepend=q[:1, :]))
    lines = ((gx + gy) > 1e-4).astype(np.float32)
    bg = _apply_lut(g, CIR) * 0.3
    return _clip(bg + lines[..., None] * np.array([0.9, 1.0, 0.7], np.float32))


def fx_flowfield(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    g = _lum(img)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=5)
    ang = np.arctan2(gy, gx) + np.pi / 2
    out = _gray3(g) * 0.15
    step = max(6, min(h, w) // 40)
    for y in range(0, h, step):
        for x in range(0, w, step):
            a = float(ang[y, x]); L = step * 0.9
            cv2.line(out, (x, y), (int(x + np.cos(a) * L), int(y + np.sin(a) * L)),
                     (0.2, 0.7, 1.0), 1, cv2.LINE_AA)
    return _clip(out)


def fx_inkbleed(img, ctx):
    base = _blur(img, 2.0)
    e = _blur(_gray3(_edges(_lum(img))), 1.5)[..., 0]
    out = base * (1.0 - 0.5 * e[..., None])
    return _clip(out * np.array([1.0, 0.98, 0.92], np.float32))


def fx_oilpaint(img, ctx):
    if HAS_CV2 and hasattr(cv2, "stylization"):
        try:
            u = (_clip(img) * 255).astype(np.uint8)
            o = cv2.stylization(u, sigma_s=40, sigma_r=0.4)
            return o.astype(np.float32) / 255.0
        except Exception:
            pass
    out = _blur(_blur(img, 1.5), 1.5)
    levels = 8
    return _clip(np.round(out * levels) / levels)


def fx_liquidmetal(img, ctx):
    g = _lum(img)
    if HAS_CV2:
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    else:
        gx = np.zeros_like(g)
        gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    spec = _clip(0.5 + gx * 2.0)
    lut = _lut_from_points([(0, (0.02, 0.03, 0.05)), (0.5, (0.4, 0.45, 0.5)),
                            (0.8, (0.8, 0.85, 0.9)), (1, (1, 1, 1))])
    return _clip(_apply_lut(_clip(g * 0.5 + spec * 0.5), lut))


def fx_refraction(img, ctx):
    h, w = img.shape[:2]
    n = _noise(h, w, ctx["rng"], 16)
    nx = _noise(h, w, np.random.default_rng(ctx["seed"] + 9), 16)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = (n - 0.5) * w * 0.05
    dy = (nx - 0.5) * h * 0.05
    out = _remap(img, np.clip(xx + dx, 0, w - 1), np.clip(yy + dy, 0, h - 1))
    return _clip(out * 0.95 + 0.05)


def fx_caustics(img, ctx):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = ctx["t"]
    c = np.sin(xx * 0.05 + t) + np.sin(yy * 0.06 - t * 0.8) + np.sin((xx + yy) * 0.04 + t * 0.5)
    c = _clip((c + 3) / 6.0) ** 2
    caust = _blur(_gray3(c), 1.5)
    out = img * np.array([0.2, 0.6, 0.9], np.float32) * 0.8 + caust * np.array([0.4, 0.8, 1.0], np.float32) * 0.6
    return _clip(out)


def fx_godrays(img, ctx):
    if not HAS_CV2:
        return _clip(img + _blur(img, 8.0) * 0.4)
    h, w = img.shape[:2]
    g = _lum(img)
    hl = _clip((g - 0.6) / 0.4)[..., None] * img
    lx, ly = w * 0.5, h * 0.1
    acc = hl.copy()
    for i in range(1, 12):
        M = cv2.getRotationMatrix2D((lx, ly), 0, 1 - i * 0.03)
        acc = acc + cv2.warpAffine(hl, M, (w, h)) * (1.0 / i)
    return _clip(img + _clip(acc * 0.4) * np.array([1.0, 0.95, 0.8], np.float32))


def fx_matrixfloor(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    out = img * 0.3
    horizon = int(h * 0.5)
    col = (0.1, 0.9, 0.5)
    for i in range(-10, 11):
        cv2.line(out, (int(w / 2 + i * w / 8), h), (int(w / 2 + i * 1.0), horizon), col, 1, cv2.LINE_AA)
    for j in range(12):
        f = ((j / 12.0) + ctx["t"] * 0.05) % 1.0
        y = int(horizon + (f ** 2) * (h - horizon))
        cv2.line(out, (0, y), (w, y), col, 1, cv2.LINE_AA)
    return _clip(out)


def fx_vaporwave(img, ctx):
    h, w = img.shape[:2]
    yy = np.linspace(0, 1, h)[:, None, None]
    grad = np.array([0.95, 0.3, 0.7], np.float32) * (1 - yy) + np.array([0.2, 0.4, 0.95], np.float32) * yy
    g = _lum(img)[..., None]
    out = grad * (0.5 + 0.5 * g)
    return _clip(1.0 - (1.0 - out) * (1.0 - img * 0.5))


def fx_aerochrome(img, ctx):
    out = np.stack([img[..., 1], img[..., 2], img[..., 0]], axis=2)
    out[..., 0] = _clip(out[..., 0] * 1.3)
    return _clip(out)


def fx_uvblacklight(img, ctx):
    sat = (img.max(2) - img.min(2))[..., None]
    glow = _blur(sat * img, 4.0) * 2.0
    return _clip(img * 0.2 + glow + np.array([0.3, 0.1, 0.6], np.float32) * 0.1)


def fx_schlieren(img, ctx):
    g = _lum(img)
    if HAS_CV2:
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    else:
        gx = np.zeros_like(g)
        gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    return _gray3(_clip(0.5 + gx * 3.0))


def fx_bokeh(img, ctx):
    if not HAS_CV2:
        return _blur(img, 4.0)
    h, w = img.shape[:2]
    g = _lum(img)
    out = _blur(img, 4.0)
    ys, xs = np.where(_clip((g - 0.7) / 0.3) > 0.05)
    if len(xs) > 0:
        rng = np.random.default_rng(ctx["seed"] + 3)
        for k in rng.choice(len(xs), min(120, len(xs)), replace=False):
            x = int(xs[k]); y = int(ys[k]); r = int(rng.integers(4, 14))
            cv2.circle(out, (x, y), r, tuple(float(c) for c in img[y, x]), -1, cv2.LINE_AA)
    return _clip(out)


def fx_prism(img, ctx):
    h, w = img.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    def shift(ch, k):
        mapx = np.clip(cx + (xx - cx) * (1 + k), 0, w - 1)
        mapy = np.clip(cy + (yy - cy) * (1 + k), 0, h - 1)
        return _remap(_gray3(ch), mapx, mapy)[..., 0]

    return _clip(np.stack([shift(img[..., 0], 0.03), img[..., 1], shift(img[..., 2], -0.03)], axis=2))


def fx_crosshatch(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    g = _lum(img)
    out = np.ones((h, w, 3), np.float32)
    thr = [0.8, 0.6, 0.4, 0.2]
    orient = [(1, 0), (0, 1), (1, 1), (1, -1)]
    sp = 5
    for lev, thrv in enumerate(thr):
        mask = g < thrv
        line = np.zeros((h, w), np.float32)
        o = orient[lev]
        if o == (1, 0):
            line[::sp, :] = 1.0
        elif o == (0, 1):
            line[:, ::sp] = 1.0
        else:
            for off in range(-h, w, sp):
                cv2.line(line, (off, 0), (off + h * o[1], h), 1.0, 1)
        out[mask & (line > 0)] = 0.05
    return _clip(out)


def fx_stipple(img, ctx):
    h, w = img.shape[:2]
    g = _lum(img)
    out = np.ones((h, w, 3), np.float32)
    rng = np.random.default_rng(ctx["seed"] + 11)
    npts = int(h * w * 0.05)
    xs = rng.integers(0, w, npts); ys = rng.integers(0, h, npts)
    keep = rng.random(npts) > g[ys, xs]
    out[ys[keep], xs[keep]] = 0.05
    return out


def fx_frost(img, ctx):
    h, w = img.shape[:2]
    n = _noise(h, w, np.random.default_rng(ctx["seed"] + 13), 30)
    crystal = _clip((n - 0.45) / 0.2)
    e = _edges(_lum(img))
    desat = _gray3(_lum(img)) * 0.5 + img * 0.5
    tint = desat * np.array([0.8, 0.95, 1.1], np.float32)
    out = _clip(tint + crystal[..., None] * 0.4 + e[..., None] * np.array([0.3, 0.4, 0.5], np.float32))
    return _clip(_blur(out, 1.0))


def fx_teslaarc(img, ctx):
    if not HAS_CV2:
        return img
    h, w = img.shape[:2]
    out = img * 0.5
    rng = np.random.default_rng(ctx["seed"] + ctx["frame"])
    ov = np.zeros_like(img)

    def bolt(x0, y0, x1, y1, disp, depth):
        if depth == 0:
            cv2.line(ov, (int(x0), int(y0)), (int(x1), int(y1)), (0.8, 0.9, 1.0), 1, cv2.LINE_AA)
            return
        mx = (x0 + x1) / 2 + rng.normal(0, disp)
        my = (y0 + y1) / 2 + rng.normal(0, disp)
        bolt(x0, y0, mx, my, disp / 2, depth - 1)
        bolt(mx, my, x1, y1, disp / 2, depth - 1)
        if rng.random() < 0.3:
            bolt(mx, my, mx + rng.normal(0, disp * 2), my + rng.normal(0, disp * 2), disp / 2, depth - 1)

    for _ in range(int(rng.integers(2, 5))):
        bolt(rng.integers(0, w), 0, rng.integers(0, w), h - 1, w * 0.08, 6)
    return _clip(out + (_blur(ov, 1.5) * 1.5 + ov))


EFFECTS = {
    # pack 1
    "thermal": fx_thermal,
    "nightvision": fx_nightvision,
    "xray": fx_xray,
    "lidar": fx_lidar,
    "wireframe": fx_wireframe,
    "holo_sweep": fx_holo_sweep,
    "hud": fx_hud,
    "sonar": fx_sonar,
    "glitch": fx_glitch,
    "hologram": fx_hologram,
    "ekg": fx_ekg,
    "coderain": fx_coderain,
    "chroma": fx_chroma,
    "falsecolor": fx_falsecolor,
    "depthmap": fx_depthmap,
    # pack 2
    "sketch": fx_sketch,
    "blueprint": fx_blueprint,
    "halftone": fx_halftone,
    "ascii": fx_ascii,
    "pixelate": fx_pixelate,
    "posterize": fx_posterize,
    "sobel": fx_sobel,
    "bloom": fx_bloom,
    "lensflare": fx_lensflare,
    "vhs": fx_vhs,
    "crt": fx_crt,
    "filmgrain": fx_filmgrain,
    "lightpaint": fx_lightpaint,
    "motionblur": fx_motionblur,
    "slitscan": fx_slitscan,
    "kaleidoscope": fx_kaleidoscope,
    "fisheye": fx_fisheye,
    "tiltshift": fx_tiltshift,
    "doubleexp": fx_doubleexp,
    "solarize": fx_solarize,
    "duotone": fx_duotone,
    "neon": fx_neon,
    "heathaze": fx_heathaze,
    "dissolve": fx_dissolve,
    "voronoi": fx_voronoi,
    "spectrum": fx_spectrum,
    "topographic": fx_topographic,
    "flowfield": fx_flowfield,
    "inkbleed": fx_inkbleed,
    "oilpaint": fx_oilpaint,
    "liquidmetal": fx_liquidmetal,
    "refraction": fx_refraction,
    "caustics": fx_caustics,
    "godrays": fx_godrays,
    "matrixfloor": fx_matrixfloor,
    "vaporwave": fx_vaporwave,
    "aerochrome": fx_aerochrome,
    "uvblacklight": fx_uvblacklight,
    "schlieren": fx_schlieren,
    "bokeh": fx_bokeh,
    "prism": fx_prism,
    "crosshatch": fx_crosshatch,
    "stipple": fx_stipple,
    "frost": fx_frost,
    "teslaarc": fx_teslaarc,
}
EFFECT_NAMES = ["none"] + list(EFFECTS.keys())
NUM_SLOTS = 8


# -----------------------------------------------------------------------------
# the node
# -----------------------------------------------------------------------------
class ScanFX:
    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "image": ("IMAGE",),
            "mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01,
                              "tooltip": "Global opacity of the whole effect stack inside the mask."}),
            "mask_feather": ("FLOAT", {"default": 4.0, "min": 0.0, "max": 256.0, "step": 0.5,
                                       "tooltip": "Soften the mask edge (pixels)."}),
            "invert_mask": ("BOOLEAN", {"default": False}),
            "animation_speed": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.1,
                                          "tooltip": "Speed of moving effects (sweep, sonar, ekg, code-rain)."}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffff}),
        }
        for i in range(1, NUM_SLOTS + 1):
            default = "thermal" if i == 1 else "none"
            required["effect_%d" % i] = (EFFECT_NAMES, {"default": default})
            required["strength_%d" % i] = ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01})
        return {"required": required, "optional": {"mask": ("MASK",)}}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "ScanFX"
    DESCRIPTION = ("Apply a stack of sci-fi scan effects (thermal/FLIR, night vision, x-ray, "
                   "LiDAR, wireframe, holo sweep, HUD, sonar, glitch, hologram, EKG, code-rain, "
                   "chromatic aberration, IR false-color, depth map) to an image or video, "
                   "confined to an optional mask.")

    def run(self, image, mix, mask_feather, invert_mask, animation_speed, seed, mask=None, **kw):
        imgs = image.detach().cpu().numpy().astype(np.float32)  # B,H,W,3
        B, H, W, _ = imgs.shape

        # build the ordered slot list once
        slots = []
        for i in range(1, NUM_SLOTS + 1):
            name = kw.get("effect_%d" % i, "none")
            s = float(kw.get("strength_%d" % i, 1.0))
            if name != "none" and s > 0:
                slots.append((EFFECTS[name], s))

        # prepare mask batch
        if mask is not None:
            m = mask.detach().cpu().numpy().astype(np.float32)
            if m.ndim == 2:
                m = m[None]
        else:
            m = None

        out = np.empty_like(imgs)
        for b in range(B):
            frame = imgs[b]
            cur = frame.copy()
            ctx = {
                "frame": b,
                "total": B,
                "t": b * animation_speed,
                "seed": int(seed),
                "rng": np.random.default_rng(int(seed) * 2654435761 % (2 ** 32) + b),
            }
            for fn, s in slots:
                try:
                    eff = fn(cur, ctx)
                    eff = np.nan_to_num(np.asarray(eff, dtype=np.float32))
                    if eff.shape != cur.shape:
                        eff = eff[..., :3]
                    cur = _clip(cur * (1.0 - s) + eff * s)
                except Exception as ex:
                    print("[ScanFX] effect '%s' failed on frame %d: %s" % (getattr(fn, "__name__", "?"), b, ex))

            # composite within mask
            if m is not None:
                mb = m[min(b, m.shape[0] - 1)]
                if mb.shape != (H, W):
                    if HAS_CV2:
                        mb = cv2.resize(mb, (W, H), interpolation=cv2.INTER_LINEAR)
                    else:
                        mb = np.ones((H, W), np.float32)
                if invert_mask:
                    mb = 1.0 - mb
                if mask_feather > 0:
                    mb = _blur(_gray3(mb), mask_feather)[..., 0]
                a = _clip(mb * mix)[..., None]
            else:
                a = np.float32(mix)

            out[b] = _clip(frame * (1.0 - a) + cur * a)

        return (torch.from_numpy(out).to(image.device),)


NODE_CLASS_MAPPINGS = {"ScanFX": ScanFX}
NODE_DISPLAY_NAME_MAPPINGS = {"ScanFX": "Scan FX (thermal / nightvision / hud / ...)"}
