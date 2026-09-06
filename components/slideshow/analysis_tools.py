"""Optional analysis backends, loaded only when their node is executed."""

import math
from fractions import Fraction

import numpy as np
from PIL import Image, ImageDraw, ImageOps


def analyze_beats(signal, sample_rate, tempo_hint=0.0, offset=0.0, cancel=lambda: None):
    import librosa
    from scipy.signal import resample_poly

    if signal.ndim != 1 or len(signal) < sample_rate * 2 or not np.isfinite(signal).all():
        raise ValueError("Beat analysis needs at least two seconds of finite audio samples.")
    if np.max(np.abs(signal)) < 1e-6:
        raise ValueError("The audio is silent; no beats can be detected.")
    cancel()
    ratio = Fraction(22050, int(sample_rate))
    signal = resample_poly(signal, ratio.numerator, ratio.denominator).astype(np.float32)
    sr, hop = 22050, 256
    envelope = librosa.onset.onset_strength(y=signal, sr=sr, hop_length=hop)
    cancel()
    tempo, frames = librosa.beat.beat_track(onset_envelope=envelope, sr=sr, hop_length=hop,
                                           bpm=float(tempo_hint) if tempo_hint > 0 else None, trim=True)
    tempo = float(np.asarray(tempo).reshape(-1)[0])
    times = librosa.frames_to_time(frames, sr=sr, hop_length=hop) + offset
    duration = len(signal) / sr
    valid = (times >= 0) & (times < duration)
    times = times[valid]
    strengths = envelope[np.asarray(frames, dtype=int)[valid]]
    if len(times) < 2 or tempo <= 0:
        raise ValueError("No stable beat sequence found. Try a tempo hint or a more rhythmic soundtrack.")
    strengths = strengths / max(float(strengths.max()), 1e-8)
    data = {"version": 1, "bpm": tempo, "duration": duration, "offset_seconds": offset,
            "times": times.tolist(), "strengths": strengths.tolist()}
    chart = Image.new("RGB", (1200, 260), (22, 24, 25))
    draw = ImageDraw.Draw(chart)
    draw.text((24, 15), f"DETECTED BEATS / {tempo:.1f} BPM / {len(times)} markers / {duration:.1f}s", fill=(240, 240, 238))
    # Summarize audio by peak bins so long tracks still have a bounded preview.
    bins = np.array_split(np.abs(signal), 1152)
    peaks = np.array([float(x.max()) if len(x) else 0 for x in bins])
    peaks /= max(float(peaks.max()), 1e-8)
    for i, peak in enumerate(peaks):
        draw.line((24 + i, 140 - peak * 67, 24 + i, 140 + peak * 67), fill=(76, 90, 104))
    for second, strength in zip(times, strengths):
        x = 24 + round(second / duration * 1152)
        draw.line((x, 75 - strength * 25, x, 220), fill=(211, 240, 74), width=1)
    for fraction in (0, 0.25, 0.5, 0.75, 1):
        draw.text((24 + fraction * 1110, 237), f"{duration * fraction:.1f}s", fill=(200, 207, 214))
    cancel()
    return data, chart


def detect_focus(image, mode="Faces", manual_x=0.5, manual_y=0.5, margin=0.15, mask=None, detector=None):
    preview = ImageOps.contain(image.convert("RGB"), (800, 800), Image.Resampling.LANCZOS)
    width, height = preview.size
    boxes = []
    method = "manual" if mode == "Manual" else "center fallback"
    if mask is not None:
        ys, xs = np.where(mask > 0.5)
        if len(xs):
            boxes = [[float(xs.min() / mask.shape[1]), float(ys.min() / mask.shape[0]),
                      float((xs.max() + 1) / mask.shape[1]), float((ys.max() + 1) / mask.shape[0])]]
            method = "mask"
        else:
            method = "empty mask / center fallback"
    elif mode == "Faces":
        if detector is None:
            from skimage import data
            from skimage.feature import Cascade
            detector = Cascade(data.lbp_frontal_face_cascade_filename())
        detections = detector.detect_multi_scale(np.asarray(preview), scale_factor=1.2, step_ratio=1.2,
                                                 min_size=(35, 35), max_size=(width, height))
        boxes = [[d["c"] / width, d["r"] / height, (d["c"] + d["width"]) / width,
                  (d["r"] + d["height"]) / height] for d in detections]
        if boxes:
            method = "faces"
    box = None
    x, y = (manual_x, manual_y) if mode == "Manual" else (0.5, 0.5)
    if boxes:
        left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
        right, bottom = max(b[2] for b in boxes), max(b[3] for b in boxes)
        dx, dy = (right - left) * margin, (bottom - top) * margin
        box = [max(0, left - dx), max(0, top - dy), min(1, right + dx), min(1, bottom + dy)]
        x, y = (left + right) / 2, (top + bottom) / 2
    if mode == "Manual" and mask is None:
        box = [max(0, x - 0.025), max(0, y - 0.025), min(1, x + 0.025), min(1, y + 0.025)]
    return {"x": float(x), "y": float(y), "box": box, "method": method}


def focus_preview(image, item):
    preview = ImageOps.contain(image, (320, 260), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(preview)
    if item.get("box"):
        left, top, right, bottom = item["box"]
        draw.rectangle((left * preview.width, top * preview.height, right * preview.width, bottom * preview.height),
                       outline=(213, 245, 60), width=3)
    x, y = item["x"] * preview.width, item["y"] * preview.height
    draw.line((x - 9, y, x + 9, y), fill=(255, 92, 92), width=2)
    draw.line((x, y - 9, x, y + 9), fill=(255, 92, 92), width=2)
    return preview
