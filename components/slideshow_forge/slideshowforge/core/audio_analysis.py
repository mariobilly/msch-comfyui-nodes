"""Beat detection for beat-synced timelines.

Classical DSP via librosa (onset-strength + tempo tracking) -- no AI model.
Consumes ComfyUI's standard AUDIO dict ({"waveform": (1,C,S) tensor,
"sample_rate": int}) rather than loading a file itself.
"""

import numpy as np
import librosa

MIN_DETECTED_BEATS = 2


def analyze_audio(waveform, sample_rate: int) -> dict:
    mono = waveform[0].mean(dim=0).detach().cpu().numpy().astype(np.float32)

    tempo, beat_frames = librosa.beat.beat_track(y=mono, sr=sample_rate)
    beats_sec = librosa.frames_to_time(beat_frames, sr=sample_rate).tolist()
    bpm = float(tempo) if np.isscalar(tempo) else float(np.asarray(tempo).reshape(-1)[0])

    if len(beats_sec) < MIN_DETECTED_BEATS:
        raise ValueError(
            "SlideshowForge: could not detect enough beats in the provided audio "
            "(too short, silent, or not rhythmic enough for beat tracking)."
        )

    return {
        "duration_sec": len(mono) / sample_rate,
        "bpm": bpm,
        "beats_sec": beats_sec,
    }
