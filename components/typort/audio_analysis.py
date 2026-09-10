"""Local audio decoding, rhythmic features and optional offline Demucs stems."""
import hashlib
import io
from fractions import Fraction
from pathlib import Path

import av
import librosa
import numpy as np
from scipy.signal import butter, sosfilt

from .project import validate_analysis


def fingerprint(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def decode(path, rate=22050, stereo=False, limit=600):
    chunks, count = [], 0
    with av.open(str(path)) as container:
        if not container.streams.audio:
            raise ValueError("This file has no audio stream.")
        resampler = av.AudioResampler(format="fltp", layout="stereo" if stereo else "mono", rate=rate)
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                values = converted.to_ndarray()[:, :max(0, round(limit * rate) - count)]
                if values.shape[1]:
                    chunks.append(values.copy())
                    count += values.shape[1]
            if count >= round(limit * rate):
                break
        if count < round(limit * rate):
            for converted in resampler.resample(None):
                values = converted.to_ndarray()[:, :max(0, round(limit * rate) - count)]
                chunks.append(values.copy())
                count += values.shape[1]
    if count < rate // 100:
        raise ValueError("The audio is empty or too short to analyze.")
    return np.concatenate(chunks, axis=1)


def features(signal, rate, reference=None):
    duration = len(signal) / rate
    if np.max(np.abs(signal)) < 1e-5:
        return {"levels": [0.0] * (int(np.ceil(duration * 60)) + 1), "hits": []}
    hop = max(1, round(rate / 60))
    rms = librosa.feature.rms(y=signal, frame_length=1024, hop_length=hop)[0]
    scale = max(float(reference if reference is not None else np.percentile(rms, 95)), 1e-5)
    times = np.arange(int(np.ceil(duration * 60)) + 1) / 60
    levels = np.clip(np.interp(times, np.arange(len(rms)) * hop / rate, rms) / scale, 0, 1)
    onset = librosa.onset.onset_strength(y=signal, sr=rate, hop_length=hop)
    hits = librosa.onset.onset_detect(onset_envelope=onset, sr=rate, hop_length=hop, units="time")
    return {"levels": np.round(levels, 4).tolist(), "hits": sorted(set(round(float(t), 5) for t in hits if 0 <= t < duration))}


def resolve_separation_device(device):
    if device not in ("auto", "cuda", "cpu"):
        raise ValueError("Separation device must be auto, cuda or cpu.")
    try:
        import torch
    except ImportError as exc:
        raise ValueError("Instrument separation requires ComfyUI's PyTorch environment.") from exc
    if device == "cpu":
        return "cpu"
    available = torch.cuda.is_available()
    if device == "cuda" and not available:
        raise ValueError("CUDA GPU is unavailable in this ComfyUI Python. Choose CPU or use a CUDA-enabled PyTorch installation.")
    return "cuda" if available else "cpu"


def load_demucs_checkpoint(checkpoint):
    """Load only the pinned artifact, using PyTorch's restricted unpickler."""
    import torch
    from demucs.htdemucs import HTDemucs
    from numpy.core.multiarray import scalar

    # Hash and deserialize the same snapshot; do not reopen a replaceable file.
    data = Path(checkpoint).read_bytes()
    if hashlib.sha256(data).hexdigest() != "8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4":
        raise ValueError("The Demucs checkpoint checksum does not match the official model.")
    # These are the fixed metadata types in the official HTDemucs artifact.
    # Never discover/allowlist globals from a supplied file or retry unsafe loads.
    allowed = [HTDemucs, Fraction, np.dtype,
               (scalar, "numpy.core.multiarray.scalar"), type(np.dtype(np.float64))]
    with torch.serialization.safe_globals(allowed):
        package = torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
    if not isinstance(package, dict) or package.get("klass") is not HTDemucs:
        raise ValueError("Expected the official HTDemucs model package.")
    return package


def separate(path, model_directory, device="cpu"):
    try:
        import torch
        from demucs.states import load_model
        from demucs.apply import apply_model
    except ImportError as exc:
        raise ValueError("Install requirements-stems.txt to enable instrument separation.") from exc
    device = resolve_separation_device(device)
    directory = Path(model_directory)
    checkpoint = directory / "955717e8-8726e21a.th"
    if not checkpoint.is_file():
        raise ValueError("The offline Demucs model is missing. Run tests/setup_stems.py explicitly before using instrument separation.")
    model = load_model(load_demucs_checkpoint(checkpoint), strict=True)
    model.eval()
    audio = torch.from_numpy(decode(path, model.samplerate, stereo=True))
    reference = audio.mean(0)
    mean, std = reference.mean(), reference.std().clamp_min(1e-5)
    normalized = (audio - mean) / std
    # Demucs moves individual chunks to CUDA; the full track and stitched output stay on CPU.
    try:
        estimates = apply_model(model, normalized[None], device=device, shifts=0, split=True,
                                overlap=0.25, progress=False, num_workers=0)[0] * std + mean
    except torch.cuda.OutOfMemoryError as exc:
        raise ValueError("Instrument separation ran out of GPU memory. Finish other GPU jobs, free VRAM, or select CPU and analyze again.") from exc
    finally:
        model.cpu()
    return {name.capitalize(): librosa.resample(stem.detach().cpu().numpy().mean(0),
            orig_sr=model.samplerate, target_sr=22050) for name, stem in zip(model.sources, estimates)}


def analyze(path, file_id, instruments=False, model_directory=None, device="auto"):
    identity = fingerprint(path)
    signal = decode(path)[0]
    rate = 22050
    duration = len(signal) / rate
    channels = {"Mix": features(signal, rate)}
    reference = max(float(np.percentile(librosa.feature.rms(y=signal)[0], 95)), 1e-5)
    for name, band, kind in (("Low band", 180, "lowpass"), ("Mid band", [180, 2500], "bandpass"),
                             ("High band", 2500, "highpass")):
        filtered = sosfilt(butter(4, band, kind, fs=rate, output="sos"), signal).astype(np.float32)
        channels[name] = features(filtered, rate, reference)
    bpm, beats = 0.0, []
    if np.max(np.abs(signal)) >= 1e-5 and duration >= 1:
        tempo, frames = librosa.beat.beat_track(y=signal, sr=rate, hop_length=256, trim=False)
        bpm = float(np.asarray(tempo).reshape(-1)[0])
        beats = [round(float(t), 5) for t in librosa.frames_to_time(frames, sr=rate, hop_length=256) if t < duration]
    if instruments:
        device = resolve_separation_device(device)
        for name, stem in separate(path, model_directory, device=device).items():
            channels[name] = features(stem[:len(signal)], rate)
    waveform = np.array([np.max(np.abs(part)) for part in np.array_split(signal, min(2400, len(signal)))])
    waveform /= max(float(waveform.max()), 1e-5)
    if fingerprint(path) != identity:
        raise ValueError("The audio file changed during analysis. Analyze it again.")
    result = dict(version=1, file=file_id, fingerprint=identity, duration=duration, rate=60,
                  bpm=round(bpm, 3), beats=beats, waveform=np.round(waveform, 4).tolist(), channels=channels)
    if instruments:
        result["separation_device"] = device
    validate_analysis(result)
    return result
