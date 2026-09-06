import numpy as np
import torch

from slideshowforge.core.audio_analysis import analyze_audio


def _click_track(bpm=120.0, duration_sec=10.0, sr=22050):
    """A percussive metronome-like click train: sharp attack + exponential
    decay, which is what librosa's onset detector is tuned for. A symmetric
    window (no attack transient) does not reliably register as an onset."""
    n = int(duration_sec * sr)
    y = np.zeros(n, dtype=np.float32)
    beat_interval = 60.0 / bpm
    click_len = int(0.05 * sr)
    decay = np.exp(-np.linspace(0, 15, click_len)).astype(np.float32)
    t = 0.0
    while t < duration_sec:
        idx = int(t * sr)
        cl = min(click_len, n - idx)
        if cl > 0:
            y[idx:idx + cl] += decay[:cl]
        t += beat_interval
    waveform = torch.from_numpy(y).unsqueeze(0).unsqueeze(0)  # (1, 1, samples)
    return waveform, sr


def test_analyze_audio_detects_roughly_correct_beat_count():
    waveform, sr = _click_track(bpm=120.0, duration_sec=10.0)
    result = analyze_audio(waveform, sr)
    expected_beats = 10.0 / (60.0 / 120.0)  # ~20 beats
    assert abs(len(result["beats_sec"]) - expected_beats) <= 4
    assert result["beats_sec"] == sorted(result["beats_sec"])
    assert result["duration_sec"] > 9.9


def test_analyze_audio_raises_on_silence():
    sr = 22050
    waveform = torch.zeros(1, 1, sr * 3)
    try:
        analyze_audio(waveform, sr)
        assert False, "expected ValueError on silent audio"
    except ValueError:
        pass
