"""Orchestrates motion + transitions + canvas fitting into one rendered clip.

VRAM-safety strategy: each segment is rendered in chunks of at most
`render_chunk_frames`, and any chunk not needed for a neighboring transition
is moved to the CPU output buffer immediately and freed from GPU memory.
Only the head (up to `incoming_k` frames) and tail (up to `outgoing_k`
frames) of a segment are ever held on GPU across iterations -- both are
small (transition lengths), regardless of how long the segment itself is.
"""

import torch

from . import canvas as canvas_mod
from . import motion as motion_mod
from . import transitions as transitions_mod

BYTES_PER_FLOAT32 = 4


def _compute_frame_accounting(durations, transition_durations, fps):
    """Cumulative-rounding frame accounting.

    Guarantees, by construction, that
    sum(segment_frames) - sum(transition_frames) == round(fps * effective_total_duration)
    exactly, regardless of independent per-item rounding noise.
    """
    n_segments = len(durations)
    n_transitions = len(transition_durations)
    cum_time = 0.0
    cum_frames = 0
    segment_frames = []
    transition_frames = []

    for i in range(n_segments):
        cum_time += durations[i]
        new_cum_frames = round(cum_time * fps)
        seg_frames = new_cum_frames - cum_frames
        if seg_frames < 1:
            raise ValueError(
                f"SlideshowForge: segment {i} (duration={durations[i]:.3f}s) produced "
                f"{seg_frames} frames at fps={fps}. Increase duration or lower fps."
            )
        segment_frames.append(seg_frames)
        cum_frames = new_cum_frames

        if i < n_transitions:
            cum_time -= transition_durations[i]
            new_cum_frames2 = round(cum_time * fps)
            t_frames = max(0, cum_frames - new_cum_frames2)
            transition_frames.append(t_frames)
            cum_frames = new_cum_frames2

    return segment_frames, transition_frames, cum_frames


def _cap_transition_frames(transition_frames, segment_frames):
    """Defensive cap so a transition can never consume an entire neighboring
    segment (leaves at least half of each neighbor's frames, minus one, as
    pure/unblended). A no-op for any normally-tuned preset -- presets already
    keep transitions much shorter than segments via timeline_builder's
    _apply_transition_repair -- this only guards pathological hand-edited
    timelines."""
    capped = list(transition_frames)
    for j, k in enumerate(capped):
        left_cap = max(0, segment_frames[j] // 2 - 1)
        right_cap = max(0, segment_frames[j + 1] // 2 - 1)
        capped[j] = min(k, left_cap, right_cap)
    return capped


def _check_output_size_budget(total_frames, height, width, max_output_bytes_gb):
    total_bytes = total_frames * height * width * 3 * BYTES_PER_FLOAT32
    budget_bytes = max_output_bytes_gb * (1024 ** 3)
    if total_bytes > budget_bytes:
        raise ValueError(
            f"SlideshowForge: rendered output would be {total_bytes / (1024**3):.2f} GB "
            f"({total_frames} frames at {width}x{height}), exceeding max_output_bytes_gb="
            f"{max_output_bytes_gb:.2f}. Shorten total_duration, lower fps/resolution, or "
            f"raise max_output_bytes_gb."
        )


def _resolve_device(device: str) -> torch.device:
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("SlideshowForge: device='cuda' requested but CUDA is not available.")
    return torch.device(device)


def _resolve_dtype(precision: str, device: torch.device) -> torch.dtype:
    if precision == "fp16" and device.type == "cuda":
        return torch.float16
    return torch.float32


class _OutputWriter:
    def __init__(self, total_frames, height, width):
        self.buffer = torch.empty((total_frames, height, width, 3), dtype=torch.float32)
        self.pos = 0

    def write(self, frames_chw: torch.Tensor):
        n = frames_chw.shape[0]
        if n == 0:
            return
        frames_hwc = frames_chw.permute(0, 2, 3, 1).to(dtype=torch.float32, device="cpu")
        self.buffer[self.pos:self.pos + n] = frames_hwc
        self.pos += n


def _render_segment_head(fitted_img_chw, motion_params, frame_count, easing_fn, device, dtype, head_size):
    """Render just the first `head_size` frames of a segment (needed to blend
    against the previous segment's tail *before* the middle is written)."""
    if head_size <= 0:
        return None
    return motion_mod.render_kenburns_segment(
        fitted_img_chw, motion_params, frame_count, easing_fn, device, dtype,
        t_start=0.0, t_end=(head_size - 1) / (frame_count - 1) if frame_count > 1 else 0.0,
        num_frames=head_size,
    )


def _render_segment_middle_and_tail(
    fitted_img_chw, motion_params, frame_count, easing_fn, device, dtype,
    render_chunk_frames, head_size, tail_size, writer,
):
    """Render the middle of a segment (writing chunks straight to `writer`
    as they're produced) and return the last `tail_size` frames for the
    caller to hold onto (for blending with the *next* segment).

    Must be called AFTER any incoming-transition blend has already been
    written -- middle frames are chronologically after the segment's head,
    so writing them first would put the transition out of order (this was
    the bug: it made the previous image flash back in right after the new
    image had already started playing alone)."""
    middle_size = frame_count - head_size - tail_size

    pos = head_size
    while pos < head_size + middle_size:
        chunk_end = min(pos + render_chunk_frames, head_size + middle_size)
        num = chunk_end - pos
        t_start = pos / (frame_count - 1) if frame_count > 1 else 0.0
        t_end = (chunk_end - 1) / (frame_count - 1) if frame_count > 1 else 0.0
        chunk = motion_mod.render_kenburns_segment(
            fitted_img_chw, motion_params, frame_count, easing_fn, device, dtype,
            t_start=t_start, t_end=t_end, num_frames=num,
        )
        writer.write(chunk)
        del chunk
        pos = chunk_end

    tail_frames = None
    if tail_size > 0:
        start_idx = frame_count - tail_size
        tail_frames = motion_mod.render_kenburns_segment(
            fitted_img_chw, motion_params, frame_count, easing_fn, device, dtype,
            t_start=start_idx / (frame_count - 1) if frame_count > 1 else 0.0,
            t_end=1.0, num_frames=tail_size,
        )

    return tail_frames


def assemble_timeline(
    images_nhwc: torch.Tensor,
    timeline: dict,
    fps: int,
    render_chunk_frames: int = 64,
    precision: str = "fp16",
    device: str = "auto",
    max_output_bytes_gb: float = 8.0,
) -> torch.Tensor:
    if timeline["fps"] != fps:
        raise ValueError(
            f"SlideshowForge: GPUMotionRenderer fps={fps} does not match "
            f"timeline_json['fps']={timeline['fps']}. They must match -- the timeline's "
            f"segment durations were solved assuming its own fps."
        )

    dev = _resolve_device(device)
    dtype = _resolve_dtype(precision, dev)

    segments = timeline["segments"]
    durations = [s["duration"] for s in segments]
    transition_durations = [
        s["transition_out"]["duration"] for s in segments if s["transition_out"] is not None
    ]

    segment_frames, transition_frames, _ = _compute_frame_accounting(
        durations, transition_durations, fps
    )
    transition_frames = _cap_transition_frames(transition_frames, segment_frames)
    # Recompute total_frames from the (possibly capped) transition_frames --
    # capping can only shrink k, which *increases* the assembled frame count
    # relative to the pre-cap estimate, so the output buffer must be sized
    # from the values actually used when writing.
    total_frames = sum(segment_frames) - sum(transition_frames)

    canvas_cfg = timeline["canvas"]
    W, H, fit_mode = canvas_cfg["width"], canvas_cfg["height"], canvas_cfg["fit"]

    _check_output_size_budget(total_frames, H, W, max_output_bytes_gb)

    images_chw_cpu = images_nhwc.permute(0, 3, 1, 2).contiguous()
    writer = _OutputWriter(total_frames, H, W)

    n_transitions = len(transition_frames)
    pending_tail = None  # previous segment's tail frames (on device), or None

    for i, seg in enumerate(segments):
        incoming_k = transition_frames[i - 1] if i > 0 else 0
        outgoing_k = transition_frames[i] if i < n_transitions else 0

        base_img_chw = images_chw_cpu[seg["image_index"]:seg["image_index"] + 1].to(device=dev, dtype=dtype)
        fitted = canvas_mod.fit_batch(base_img_chw, W, H, fit_mode)
        del base_img_chw

        easing_fn = motion_mod.get_easing_fn(seg["motion"]["easing"])

        # Render (and blend/write) the head FIRST -- it's chronologically
        # before the middle, since it's what the incoming transition
        # replaces. Writing the middle before this would put the previous
        # segment's tail-blend after the new image already played alone.
        head_frames = _render_segment_head(
            fitted, seg["motion"]["params"], segment_frames[i], easing_fn, dev, dtype, incoming_k
        )

        if incoming_k > 0:
            transition = segments[i - 1]["transition_out"]
            trans_easing_fn = motion_mod.get_easing_fn(transition["easing"])
            blended = transitions_mod.render_transition(pending_tail, head_frames, transition, trans_easing_fn)
            writer.write(blended)
            del blended, head_frames, pending_tail
        elif head_frames is not None:
            writer.write(head_frames)
            del head_frames

        tail_frames = _render_segment_middle_and_tail(
            fitted, seg["motion"]["params"], segment_frames[i], easing_fn, dev, dtype,
            render_chunk_frames, incoming_k, outgoing_k, writer,
        )
        del fitted

        pending_tail = tail_frames

    if pending_tail is not None:
        writer.write(pending_tail)
        del pending_tail

    if writer.pos != total_frames:
        raise RuntimeError(
            f"SlideshowForge internal error: wrote {writer.pos} frames, expected {total_frames}."
        )

    return writer.buffer
