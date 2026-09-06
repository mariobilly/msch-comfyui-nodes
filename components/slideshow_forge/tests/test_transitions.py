import torch

from slideshowforge.core.motion import get_easing_fn
from slideshowforge.core import transitions as T

LINEAR = get_easing_fn("linear")


def _pair(H=8, W=8, k=6):
    A = torch.zeros(k, 3, H, W)
    B = torch.ones(k, 3, H, W)
    return A, B


def test_crossfade_boundaries():
    A, B = _pair()
    progress = torch.linspace(0.0, 1.0, A.shape[0])
    out = T.crossfade(A, B, progress)
    assert torch.allclose(out[0], A[0])
    assert torch.allclose(out[-1], B[-1])


def test_wipe_boundaries_all_directions():
    A, B = _pair()
    progress = torch.linspace(0.0, 1.0, A.shape[0])
    for direction in ("left", "right", "up", "down", "diagonal_tl", "diagonal_br"):
        out = T.wipe(A, B, progress, direction, feather_px=2.0)
        assert torch.allclose(out[0], A[0], atol=1e-5), direction
        assert torch.allclose(out[-1], B[-1], atol=1e-5), direction


def test_blur_dissolve_boundaries():
    A, B = _pair()
    progress = torch.linspace(0.0, 1.0, A.shape[0])
    out = T.blur_dissolve(A, B, progress, max_sigma=4.0)
    # at progress=0/1, sigma = max_sigma*sin(pi*t) is also 0, so no blur applied.
    assert torch.allclose(out[0], A[0], atol=1e-4)
    assert torch.allclose(out[-1], B[-1], atol=1e-4)


def test_render_transition_dispatch():
    A, B = _pair()
    for ttype, params in [
        ("crossfade", {}),
        ("wipe_left", {"feather_px": 4.0}),
        ("diagonal_wipe_br", {"feather_px": 4.0}),
        ("blur_dissolve", {"max_sigma": 3.0}),
    ]:
        transition = {"type": ttype, "params": params}
        out = T.render_transition(A, B, transition, LINEAR)
        assert out.shape == A.shape
        assert torch.isfinite(out).all()
