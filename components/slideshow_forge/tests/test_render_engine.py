import torch

from slideshowforge.core.render_engine import assemble_timeline
from slideshowforge.core.timeline_builder import build_timeline

CANVAS_W, CANVAS_H = 16, 12


def _flat_motion():
    return {
        "type": "static",
        "easing": "linear",
        "params": {
            "start_scale": 1.0, "end_scale": 1.0,
            "pan_x_start": 0.0, "pan_x_end": 0.0,
            "pan_y_start": 0.0, "pan_y_end": 0.0,
            "rotation_deg_start": 0.0, "rotation_deg_end": 0.0,
        },
    }


def _hand_built_timeline(fps=10):
    # 3 segments of 2.0s, 2 transitions of 0.5s -> effective total = 5.0s.
    return {
        "version": 1, "seed": 0, "preset": "test", "fps": fps,
        "canvas": {"width": CANVAS_W, "height": CANVAS_H, "fit": "cover"},
        "total_duration": 5.0, "duration_solve_residual": 0.0, "loop": False,
        "segments": [
            {"index": 0, "image_index": 0, "duration": 2.0, "layout": "full_bleed",
             "motion": _flat_motion(),
             "transition_out": {"type": "crossfade", "duration": 0.5, "easing": "linear", "params": {}}},
            {"index": 1, "image_index": 1, "duration": 2.0, "layout": "full_bleed",
             "motion": _flat_motion(),
             "transition_out": {"type": "crossfade", "duration": 0.5, "easing": "linear", "params": {}}},
            {"index": 2, "image_index": 2, "duration": 2.0, "layout": "full_bleed",
             "motion": _flat_motion(),
             "transition_out": None},
        ],
    }


def _synthetic_images(n=3, h=20, w=24):
    return torch.rand(n, h, w, 3)


def test_hand_built_timeline_exact_frame_count():
    timeline = _hand_built_timeline(fps=10)
    images = _synthetic_images()
    out = assemble_timeline(images, timeline, fps=10, device="cpu", precision="fp32")
    assert out.shape == (50, CANVAS_H, CANVAS_W, 3)


def test_output_is_channel_last_and_finite():
    timeline = _hand_built_timeline(fps=10)
    images = _synthetic_images()
    out = assemble_timeline(images, timeline, fps=10, device="cpu", precision="fp32")
    assert out.dtype == torch.float32
    assert torch.isfinite(out).all()


def test_fps_mismatch_raises():
    timeline = _hand_built_timeline(fps=10)
    images = _synthetic_images()
    try:
        assemble_timeline(images, timeline, fps=24, device="cpu", precision="fp32")
        assert False, "expected ValueError on fps mismatch"
    except ValueError:
        pass


def test_integration_with_timeline_builder_exact_frame_count():
    timeline = build_timeline(
        image_count=5, preset_name="classic_ken_burns", duration_mode="total_duration",
        total_duration=10.0, per_image_duration=3.0, fps=12, seed=7,
        canvas_width=CANVAS_W, canvas_height=CANVAS_H,
    )
    images = _synthetic_images(n=5)
    out = assemble_timeline(images, timeline, fps=12, device="cpu", precision="fp32")
    expected_frames = round(12 * timeline["total_duration"])
    assert out.shape[0] == expected_frames


def _solid_color_images():
    # image0=red, image1=green, image2=blue -- constant color per image, no
    # motion, so every output frame should itself be a uniform color (or a
    # uniform crossfade blend of two adjacent colors during a transition).
    h, w = 12, 16
    images = torch.zeros(3, h, w, 3)
    images[0, :, :, 0] = 1.0  # red
    images[1, :, :, 1] = 1.0  # green
    images[2, :, :, 2] = 1.0  # blue
    return images


def test_transition_frames_are_not_written_out_of_order():
    """Regression test for a real bug: each segment's own ('middle') frames
    were being written to the output BEFORE the transition blending it in
    from the previous segment, making the previous image flash back in
    right after the new image had already played alone. Using solid-color
    images (red -> green -> blue), a scalar 'progress' (0=pure red, 1=pure
    green, 2=pure blue) must be non-decreasing across every output frame --
    any dip means a previous color reappeared out of order."""
    timeline = _hand_built_timeline(fps=10)
    images = _solid_color_images()
    out = assemble_timeline(images, timeline, fps=10, device="cpu", precision="fp32")

    mean_per_frame = out.mean(dim=(1, 2))  # (N, 3) -- mean R,G,B per frame
    progress = mean_per_frame[:, 1] + 2.0 * mean_per_frame[:, 2]  # 0=red,1=green,2=blue

    diffs = progress[1:] - progress[:-1]
    min_diff = diffs.min().item()
    assert min_diff >= -1e-4, (
        f"progress decreased between consecutive frames (min diff={min_diff}) -- "
        "a previous segment's color reappeared out of order"
    )
    # Sanity: it must actually traverse the full red->green->blue range, not
    # just be trivially constant.
    assert progress[0].item() < 0.1
    assert progress[-1].item() > 1.9


def test_single_segment_no_transitions():
    timeline = build_timeline(
        image_count=1, preset_name="classic_ken_burns", duration_mode="per_image_duration",
        total_duration=10.0, per_image_duration=2.0, fps=10, seed=1,
        canvas_width=CANVAS_W, canvas_height=CANVAS_H,
    )
    images = _synthetic_images(n=1)
    out = assemble_timeline(images, timeline, fps=10, device="cpu", precision="fp32")
    assert out.shape[0] == 20
