"""librosa/soundfile-based audio analysis: BeatMap extraction + waveform peaks.

Depends on librosa/soundfile/numpy (not ComfyUI/torch), so it's importable
under plain pytest as long as those third-party packages are installed --
which they are in the embedded ComfyUI Python environment this pack targets.

Both functions here are synchronous/blocking by design. Wrapping them in
`asyncio.to_thread` is the responsibility of mscha2v/server/routes.py, never
this module, so this module stays trivially unit-testable without an event
loop.
"""

from __future__ import annotations

import numpy as np
import soundfile as sf

from .schemas import BeatMap


def _to_float(value) -> float:
    """librosa's beat_track can return tempo as a scalar, 0-d array, or
    length-1 array depending on version/params -- normalize to a plain float.
    """
    arr = np.asarray(value)
    if arr.ndim == 0:
        return float(arr)
    return float(arr.reshape(-1)[0]) if arr.size else 0.0


def analyze_audio(path: str, source: str = "full") -> BeatMap:
    """Run beat/onset/tempo analysis on the audio file at `path`.

    `source`:
      - "full": analyze the mixed signal as-is.
      - "drums" / "percussive": run harmonic-percussive source separation
        (librosa.effects.hpss) first and analyze only the percussive
        component -- usually gives cleaner beat tracking on music with a
        prominent kick/snare pattern.

    `downbeats_sec` is approximated as every 4th detected beat starting at
    the first beat (a 4/4-meter heuristic) -- librosa has no native
    downbeat/meter detector, so this is a documented approximation, not a
    true measure-boundary detection.
    """
    import librosa

    if source not in ("full", "drums", "percussive"):
        raise ValueError(f"source must be one of 'full'/'drums'/'percussive', got {source!r}")

    y, sr = librosa.load(path, sr=None, mono=True)
    duration_sec = float(librosa.get_duration(y=y, sr=sr))

    y_analysis = y
    if source in ("drums", "percussive"):
        _, y_analysis = librosa.effects.hpss(y)

    tempo, _beat_frames = librosa.beat.beat_track(y=y_analysis, sr=sr, units="time")
    beats_sec = [float(t) for t in np.atleast_1d(_beat_frames)]

    onset_times = librosa.onset.onset_detect(y=y_analysis, sr=sr, units="time")
    onsets_sec = [float(t) for t in np.atleast_1d(onset_times)]

    downbeats_sec = beats_sec[0::4] if beats_sec else []
    offset_ms = beats_sec[0] * 1000.0 if beats_sec else 0.0

    return BeatMap(
        duration_sec=duration_sec,
        sr=int(sr),
        bpm=_to_float(tempo),
        beats_sec=beats_sec,
        onsets_sec=onsets_sec,
        downbeats_sec=downbeats_sec,
        analysis_source=source,
        offset_ms=offset_ms,
    )


def downsample_waveform_peaks(path: str, px: int, t0: float, t1: float) -> list[tuple[float, float]]:
    """Downsample the waveform in [t0, t1) seconds into `px` (min, max) peak
    pairs, suitable for drawing a canvas waveform without shipping raw
    samples to the browser.
    """
    if px <= 0:
        raise ValueError("px must be > 0")
    if t1 <= t0:
        return [(0.0, 0.0)] * px

    info = sf.info(path)
    sr = info.samplerate
    total_frames = info.frames

    start_frame = max(0, min(total_frames, int(t0 * sr)))
    end_frame = max(0, min(total_frames, int(t1 * sr)))
    if end_frame <= start_frame:
        return [(0.0, 0.0)] * px

    data, _ = sf.read(path, start=start_frame, frames=end_frame - start_frame, dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)

    n = len(data)
    if n == 0:
        return [(0.0, 0.0)] * px

    bucket_edges = np.linspace(0, n, px + 1).astype(np.int64)
    peaks: list[tuple[float, float]] = []
    for i in range(px):
        lo, hi = bucket_edges[i], bucket_edges[i + 1]
        if hi <= lo:
            peaks.append((0.0, 0.0))
            continue
        chunk = data[lo:hi]
        peaks.append((float(chunk.min()), float(chunk.max())))
    return peaks
