import torch

from slideshowforge.core.motion import get_easing_fn, render_kenburns_segment

EASING = get_easing_fn("linear")


def _base_params(**overrides):
    p = {
        "start_scale": 1.0, "end_scale": 1.0,
        "pan_x_start": 0.0, "pan_x_end": 0.0,
        "pan_y_start": 0.0, "pan_y_end": 0.0,
        "rotation_deg_start": 0.0, "rotation_deg_end": 0.0,
    }
    p.update(overrides)
    return p


def _checkerboard(H=64, W=96):
    img = torch.zeros(1, 3, H, W)
    img[:, :, :, : W // 2] = torch.tensor([1.0, 0.0, 0.0]).view(1, 3, 1, 1)  # left = red
    img[:, :, :, W // 2:] = torch.tensor([0.0, 0.0, 1.0]).view(1, 3, 1, 1)   # right = blue
    return img


def test_shape_and_no_nan():
    img = _checkerboard()
    params = _base_params(end_scale=1.15, pan_x_end=0.05, pan_y_end=-0.03, rotation_deg_end=5.0)
    frames = render_kenburns_segment(img, params, frame_count=10, easing_fn=EASING,
                                      device="cpu", dtype=torch.float32)
    assert frames.shape == (10, 3, 64, 96)
    assert torch.isfinite(frames).all()


def test_static_motion_reproduces_source():
    img = _checkerboard()
    params = _base_params()
    frames = render_kenburns_segment(img, params, frame_count=1, easing_fn=EASING,
                                      device="cpu", dtype=torch.float32)
    assert torch.allclose(frames, img, atol=1e-4)


def test_pan_is_fully_clamped_at_scale_one():
    """At scale=1.0 the valid pan offset is exactly 0 (no source content exists
    beyond the canvas-fitted edges), so an out-of-range pan request must be
    clamped away entirely and reproduce the unpanned frame -- this is the
    mechanism that prevents reflection-padding artifacts."""
    img = _checkerboard()
    extreme = _base_params(pan_x_end=5.0, pan_y_end=-5.0)
    unpanned = _base_params()

    frames_extreme = render_kenburns_segment(img, extreme, frame_count=1, easing_fn=EASING,
                                              device="cpu", dtype=torch.float32)
    frames_unpanned = render_kenburns_segment(img, unpanned, frame_count=1, easing_fn=EASING,
                                               device="cpu", dtype=torch.float32)
    assert torch.allclose(frames_extreme, frames_unpanned, atol=1e-4)


def test_pan_clamp_scales_with_zoom():
    """At scale=2.0 the valid pan offset is +-(1 - 1/2) = +-0.5; an
    out-of-range request should clamp to exactly that, not to 0 and not
    pass through unclamped."""
    img = _checkerboard()
    extreme = _base_params(start_scale=2.0, end_scale=2.0, pan_x_end=5.0)
    at_limit = _base_params(start_scale=2.0, end_scale=2.0, pan_x_end=0.5)
    beyond_limit = _base_params(start_scale=2.0, end_scale=2.0, pan_x_end=0.6)

    frames_extreme = render_kenburns_segment(img, extreme, frame_count=1, easing_fn=EASING,
                                              device="cpu", dtype=torch.float32)
    frames_at_limit = render_kenburns_segment(img, at_limit, frame_count=1, easing_fn=EASING,
                                               device="cpu", dtype=torch.float32)
    frames_beyond_limit = render_kenburns_segment(img, beyond_limit, frame_count=1, easing_fn=EASING,
                                                   device="cpu", dtype=torch.float32)
    assert torch.allclose(frames_extreme, frames_at_limit, atol=1e-4)
    assert torch.allclose(frames_beyond_limit, frames_at_limit, atol=1e-4)


def test_chunked_subrange_matches_full_render():
    """A sub-range render (t_start/t_end/num_frames) at a given global frame
    index must match that same frame from a full-segment render -- this is
    the correctness contract render_engine's chunking relies on."""
    img = _checkerboard()
    params = _base_params(end_scale=1.2, pan_x_end=0.08, rotation_deg_end=8.0)
    frame_count = 20

    full = render_kenburns_segment(img, params, frame_count=frame_count, easing_fn=EASING,
                                    device="cpu", dtype=torch.float32)

    chunk_start, chunk_end = 5, 12  # sub-range [5, 12)
    t_start = chunk_start / (frame_count - 1)
    t_end = (chunk_end - 1) / (frame_count - 1)
    chunk = render_kenburns_segment(img, params, frame_count=frame_count, easing_fn=EASING,
                                     device="cpu", dtype=torch.float32,
                                     t_start=t_start, t_end=t_end, num_frames=chunk_end - chunk_start)

    assert torch.allclose(chunk, full[chunk_start:chunk_end], atol=1e-5)
