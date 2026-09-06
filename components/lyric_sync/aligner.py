"""
Lyric Sync — alignment core.

Takes a song (audio tensor) + pasted lyrics text and returns a list of timed
lyric lines:  [{idx, text, translation, start, end, words:[{w, start, end}]}, ...]

Strategy (see project plan): Whisper mishears sung vocals, so we use WhisperX only
to build a reliable *word timeline* from the audio, then snap the user's pasted
lyrics (ground-truth words) onto that timeline via token sequence-matching. Words
the transcription missed are filled by linear interpolation. If WhisperX produces
nothing usable, we fall back to distributing the lyric lines evenly across the
song duration so the node never hard-fails.

WhisperX lives in a separate Python 3.13 env on this machine, so we call its CLI
via subprocess rather than importing it into ComfyUI's embedded interpreter.
"""

import os
import re
import sys
import json
import shutil
import difflib
import tempfile
import subprocess
import wave

import numpy as np


# Conventional per-user Python 3.13 location on Windows, after explicit path/PATH.
_KNOWN_WHISPERX = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local")),
    "Programs", "Python", "Python313", "Scripts", "whisperx.exe",
)

_WORD_RE = re.compile(r"[^\W\d_]+|\d+", re.UNICODE)


def resolve_whisperx(explicit=""):
    """Return a usable path to the whisperx executable, or None."""
    explicit = (explicit or "").strip().strip('"')
    if explicit and os.path.isfile(explicit):
        return explicit
    found = shutil.which("whisperx")
    if found:
        return found
    if os.path.isfile(_KNOWN_WHISPERX):
        return _KNOWN_WHISPERX
    return None


def tensor_to_wav(audio, path):
    """Write a ComfyUI AUDIO dict to a 16-bit mono WAV at its native sample rate.

    audio = {"waveform": Tensor[batch, channels, samples], "sample_rate": int}
    """
    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])

    data = waveform.detach().cpu().numpy()
    data = np.squeeze(data)              # drop batch dim(s)
    if data.ndim == 2:                   # [channels, samples] -> mono
        data = np.mean(data, axis=0)
    elif data.ndim > 2:
        raise ValueError(f"Unsupported audio shape: {data.shape}")

    data = np.clip(data, -1.0, 1.0)
    pcm = (data * 32767.0).astype(np.int16)

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())

    return len(data) / float(sample_rate)  # duration in seconds


def run_whisperx(wav_path, out_dir, language="auto", model="medium", exe=None):
    """Run the WhisperX CLI and return the parsed JSON dict (or None on failure)."""
    exe = exe or resolve_whisperx()
    if not exe:
        print("[LyricSync] whisperx executable not found; falling back to even timing.")
        return None

    cmd = [
        exe, wav_path,
        "--model", model,
        "--compute_type", "float32",
        "--device", "cpu",
        "--output_format", "json",
        "--output_dir", out_dir,
    ]
    if language and language.lower() != "auto":
        cmd += ["--language", language]

    print("[LyricSync] running:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except Exception as e:
        print(f"[LyricSync] whisperx failed to launch: {e}")
        return None

    if proc.returncode != 0:
        print(f"[LyricSync] whisperx exited {proc.returncode}.")
        if proc.stderr:
            print(proc.stderr[-2000:])

    # WhisperX writes <wav_basename>.json into out_dir regardless of small warnings.
    base = os.path.splitext(os.path.basename(wav_path))[0]
    json_path = os.path.join(out_dir, base + ".json")
    if not os.path.isfile(json_path):
        # Some versions name by the full input; grab any .json in the dir.
        candidates = [f for f in os.listdir(out_dir) if f.endswith(".json")]
        if not candidates:
            return None
        json_path = os.path.join(out_dir, candidates[0])

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[LyricSync] could not read whisperx json: {e}")
        return None


def _flat_words(wx_json):
    """Extract a flat [{w, start, end}] list from a WhisperX json result."""
    words = []
    if not wx_json:
        return words

    # Preferred: top-level word_segments[]
    for w in wx_json.get("word_segments", []) or []:
        if "start" in w and "end" in w and w.get("word"):
            words.append({"w": w["word"], "start": float(w["start"]), "end": float(w["end"])})

    if words:
        return words

    # Fallback: dig into segments[].words[]
    for seg in wx_json.get("segments", []) or []:
        for w in seg.get("words", []) or []:
            if "start" in w and "end" in w and w.get("word"):
                words.append({"w": w["word"], "start": float(w["start"]), "end": float(w["end"])})
    return words


def _norm(token):
    return token.lower().strip()


def _tokenize_lines(lyrics):
    """Split lyrics into lines, each line into normalized word tokens.

    Returns (lines, tokens, owner) where:
      lines  = list of original (stripped) line strings, blank lines dropped
      tokens = flat list of normalized tokens across all kept lines
      owner  = parallel list mapping each token -> its line index
    """
    lines, tokens, owner = [], [], []
    for raw in lyrics.splitlines():
        line = raw.strip()
        if not line:
            continue
        line_idx = len(lines)
        line_tokens = [_norm(t) for t in _WORD_RE.findall(line)]
        if not line_tokens:
            # keep purely-symbolic lines as display-only (no timing anchor)
            lines.append(line)
            continue
        lines.append(line)
        for t in line_tokens:
            tokens.append(t)
            owner.append(line_idx)
    return lines, tokens, owner


def _snap_times(lyric_tokens, wx_words):
    """Assign a (start, end) to every lyric token by matching to wx_words.

    Uses difflib to find equal runs, copies timings on matches, and linearly
    interpolates timing for unmatched lyric tokens between known anchors.
    Returns a list of (start, end) parallel to lyric_tokens (entries may be None
    before interpolation; this function fills them).
    """
    n = len(lyric_tokens)
    times = [None] * n
    if not wx_words:
        return times

    wx_norm = [_norm(w["w"]) for w in wx_words]
    sm = difflib.SequenceMatcher(a=lyric_tokens, b=wx_norm, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                wx = wx_words[j1 + k]
                times[i1 + k] = (wx["start"], wx["end"])

    # Interpolate gaps between anchored tokens.
    anchored = [i for i, t in enumerate(times) if t is not None]
    if not anchored:
        # No matches at all -> spread across the wx span.
        span_start = wx_words[0]["start"]
        span_end = wx_words[-1]["end"]
        step = (span_end - span_start) / max(1, n)
        for i in range(n):
            s = span_start + i * step
            times[i] = (s, s + step)
        return times

    first, last = anchored[0], anchored[-1]
    # Leading unmatched tokens: back off before the first anchor.
    fs = times[first][0]
    for i in range(first):
        frac = (i + 1) / (first + 1)
        times[i] = (max(0.0, fs * frac), fs)
    # Trailing unmatched tokens: extend after the last anchor.
    le = times[last][1]
    for i in range(last + 1, n):
        times[i] = (le, le)
    # Interior gaps: linear interpolation between surrounding anchors.
    for a, b in zip(anchored, anchored[1:]):
        if b - a <= 1:
            continue
        t0 = times[a][1]
        t1 = times[b][0]
        gap = b - a
        for k in range(1, gap):
            frac0 = (k - 1) / gap
            frac1 = k / gap
            times[a + k] = (t0 + (t1 - t0) * frac0, t0 + (t1 - t0) * frac1)
    return times


def align_lyrics(audio, lyrics, translation="", language="auto",
                 model="medium", whisperx_exe="", duration_hint=0.0):
    """Top-level: returns the LYRIC_TIMING list described in the module docstring."""
    lines, tokens, owner = _tokenize_lines(lyrics)
    trans_lines = [l.strip() for l in (translation or "").splitlines() if l.strip()]

    if not lines:
        return []

    tmp_dir = tempfile.mkdtemp(prefix="lyricsync_")
    wav_path = os.path.join(tmp_dir, "song.wav")
    try:
        duration = tensor_to_wav(audio, wav_path)
        duration = duration or duration_hint
        wx_json = run_whisperx(wav_path, tmp_dir, language=language,
                               model=model, exe=whisperx_exe)
        wx_words = _flat_words(wx_json)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    timing = _build_lines(lines, tokens, owner, wx_words, trans_lines, duration)
    print(f"[LyricSync] aligned {len(timing)} lines "
          f"({'whisperx' if wx_words else 'even-fallback'}).")
    return timing


def _build_lines(lines, tokens, owner, wx_words, trans_lines, duration):
    """Assemble per-line timing from token-level snapping (or even fallback)."""
    # Per-token (start, end).
    if wx_words and tokens:
        token_times = _snap_times(tokens, wx_words)
    else:
        token_times = None

    # Group token times by line.
    line_words = {i: [] for i in range(len(lines))}
    if token_times is not None:
        for tok, line_idx, tt in zip(tokens, owner, token_times):
            if tt is None:
                continue
            line_words[line_idx].append({"w": tok, "start": tt[0], "end": tt[1]})

    result = []
    # Determine which lines actually have timing.
    timed = {i: ws for i, ws in line_words.items() if ws}

    if not timed:
        # Even fallback across the whole song.
        total = duration if duration > 0 else float(len(lines))
        step = total / max(1, len(lines))
        for i, text in enumerate(lines):
            s = i * step
            e = s + step
            result.append({
                "idx": i, "text": text,
                "translation": trans_lines[i] if i < len(trans_lines) else "",
                "start": round(s, 3), "end": round(e, 3), "words": [],
            })
        return result

    # Build from snapped timings; clamp each line's end to the next line's start.
    starts = {}
    ends = {}
    for i in range(len(lines)):
        ws = line_words.get(i) or []
        if ws:
            starts[i] = min(w["start"] for w in ws)
            ends[i] = max(w["end"] for w in ws)

    ordered = sorted(starts.keys())
    for pos, i in enumerate(ordered):
        s = starts[i]
        e = ends[i]
        # clamp to next timed line's start to avoid overlap
        if pos + 1 < len(ordered):
            nxt = starts[ordered[pos + 1]]
            if e > nxt:
                e = nxt
        if e <= s:
            e = s + 0.5
        result.append({
            "idx": i, "text": lines[i],
            "translation": trans_lines[i] if i < len(trans_lines) else "",
            "start": round(s, 3), "end": round(e, 3),
            "words": [{"w": w["w"], "start": round(w["start"], 3),
                       "end": round(w["end"], 3)} for w in line_words[i]],
        })

    result.sort(key=lambda d: d["start"])
    return result


# Allow standalone testing:  python aligner.py song.wav lyrics.txt [lang] [model]
if __name__ == "__main__":
    import torchaudio  # only needed for the CLI self-test

    wav = sys.argv[1]
    lyr = open(sys.argv[2], "r", encoding="utf-8").read()
    lang = sys.argv[3] if len(sys.argv) > 3 else "auto"
    mdl = sys.argv[4] if len(sys.argv) > 4 else "medium"

    wav_t, sr = torchaudio.load(wav)
    audio = {"waveform": wav_t.unsqueeze(0), "sample_rate": sr}
    out = align_lyrics(audio, lyr, language=lang, model=mdl)
    print(json.dumps(out, ensure_ascii=False, indent=2))
