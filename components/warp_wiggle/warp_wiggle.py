"""
WarpWiggle Transition node for ComfyUI.

Blends two image sequences (video clips, as ComfyUI IMAGE batches) with a
time-slice / displacement "warp and wiggle" transition, inspired by the
@thesystms TimeSlice look: the frame breaks into bands / blocks that each get
pushed around by an animated displacement field while the wipe sweeps from
clip A to clip B. Black borders appear where slices push out of frame.

Input/Output: IMAGE (torch tensor [N, H, W, C], float32 0..1) — pairs cleanly
with VideoHelperSuite Load Video / Video Combine.
"""

import math
import torch
import torch.nn.functional as F


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _ease(p, mode):
    if mode == "linear":
        return p
    if mode == "ease_in":
        return p * p
    if mode == "ease_out":
        return 1.0 - (1.0 - p) ** 2
    if mode == "ease_in_out":
        return 0.5 - 0.5 * math.cos(math.pi * p)
    if mode == "snap":
        # mostly hold, then a fast flick in the middle third
        if p < 0.4:
            return 0.0
        if p > 0.6:
            return 1.0
        return (p - 0.4) / 0.2
    return p


def _value_noise(h, w, cells, seed, device):
    """Smooth value noise in [-1, 1], shape [H, W]."""
    cells = max(2, int(cells))
    g = torch.Generator().manual_seed(int(seed) & 0x7FFFFFFF)
    base = torch.rand((1, 1, cells, cells), generator=g)
    up = F.interpolate(base, size=(h, w), mode="bicubic", align_corners=True)
    return (up[0, 0] * 2.0 - 1.0).to(device)


def _block_noise(h, w, block_px, seed, device):
    """Hard-edged per-block value noise in [-1, 1], shape [H, W] (stair-step look)."""
    bh = max(1, h // max(1, int(block_px)))
    bw = max(1, w // max(1, int(block_px)))
    g = torch.Generator().manual_seed(int(seed) & 0x7FFFFFFF)
    base = torch.rand((1, 1, bh, bw), generator=g)
    up = F.interpolate(base, size=(h, w), mode="nearest")
    return (up[0, 0] * 2.0 - 1.0).to(device)


def _match(a, b):
    """Make sequence b match a's H, W, C (resize / pad channels)."""
    _, ha, wa, ca = a.shape
    _, hb, wb, cb = b.shape
    if (hb, wb) != (ha, wa):
        b = b.permute(0, 3, 1, 2)
        b = F.interpolate(b, size=(ha, wa), mode="bilinear", align_corners=False)
        b = b.permute(0, 2, 3, 1)
    if cb != ca:
        if cb == 4 and ca == 3:
            b = b[..., :3]
        elif cb == 3 and ca == 4:
            alpha = torch.ones_like(b[..., :1])
            b = torch.cat([b, alpha], dim=-1)
    return b


# ----------------------------------------------------------------------------
# node
# ----------------------------------------------------------------------------

class WarpWiggleTransition:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images_a": ("IMAGE",),
                "images_b": ("IMAGE",),
                "transition_frames": ("INT", {"default": 16, "min": 2, "max": 600}),
                "warp_pattern": (
                    ["horizontal_bands", "vertical_bands", "blocks",
                     "radial", "slit_scan"],
                    {"default": "horizontal_bands"},
                ),
                "warp_strength": ("FLOAT", {"default": 0.18, "min": 0.0, "max": 1.0, "step": 0.01}),
                "warp_frequency": ("FLOAT", {"default": 5.0, "min": 0.5, "max": 60.0, "step": 0.5}),
                "wiggle_amplitude": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 0.5, "step": 0.01}),
                "wiggle_frequency": ("FLOAT", {"default": 7.0, "min": 0.5, "max": 60.0, "step": 0.5}),
                "wiggle_axis": (["horizontal", "vertical", "both"], {"default": "both"}),
                "block_size": ("INT", {"default": 48, "min": 4, "max": 512}),
                "noise_amount": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01}),
                "sweep_direction": (
                    ["top_to_bottom", "bottom_to_top", "left_to_right",
                     "right_to_left", "center_out", "random_blocks"],
                    {"default": "top_to_bottom"},
                ),
                "sweep_softness": ("FLOAT", {"default": 0.22, "min": 0.01, "max": 1.0, "step": 0.01}),
                "easing": (["ease_in_out", "linear", "ease_in", "ease_out", "snap"],
                           {"default": "ease_in_out"}),
                "edge_mode": (["zeros", "border", "reflection"], {"default": "zeros"}),
                "chromatic_aberration": ("FLOAT", {"default": 0.3, "min": 0.0, "max": 1.0, "step": 0.01}),
                "parallax": ("FLOAT", {"default": 0.5, "min": -1.0, "max": 1.0, "step": 0.05}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "render"
    CATEGORY = "WarpWiggle"

    # ------------------------------------------------------------------
    def _displacement(self, H, W, p, params, dev, noise_x, noise_y, blk):
        """Return (dx, dy) displacement grids in normalized grid units, plus a
        boundary-wobble field used to warp the A/B wipe edge. env shapes the
        bell so the warp is calm -> wild -> calm."""
        env = math.sin(math.pi * min(max(p, 0.0), 1.0))  # 0..1..0

        ys = torch.linspace(0.0, 1.0, H, device=dev).view(H, 1).expand(H, W)
        xs = torch.linspace(0.0, 1.0, W, device=dev).view(1, W).expand(H, W)

        STR = params["warp_strength"] * 2.0          # grid units (full frame = 2.0)
        WF = params["warp_frequency"]
        phase = p * 2.0 * math.pi

        dx = torch.zeros((H, W), device=dev)
        dy = torch.zeros((H, W), device=dev)

        pat = params["warp_pattern"]
        if pat == "horizontal_bands":
            dx = dx + STR * torch.sin(2 * math.pi * WF * ys + phase)
        elif pat == "vertical_bands":
            dy = dy + STR * torch.sin(2 * math.pi * WF * xs + phase)
        elif pat == "blocks":
            dx = dx + STR * blk[0]
            dy = dy + STR * blk[1]
        elif pat == "radial":
            cx, cy = xs - 0.5, ys - 0.5
            r = torch.sqrt(cx * cx + cy * cy) + 1e-6
            wave = STR * torch.sin(2 * math.pi * WF * r - phase)
            dx = dx + wave * (cx / r)
            dy = dy + wave * (cy / r)
        elif pat == "slit_scan":
            # each horizontal band shears horizontally by a time-varying amount
            band = torch.floor(ys * WF) / max(1.0, WF)
            dx = dx + STR * (band - 0.5) * 2.0 * math.sin(phase)
            dy = dy + STR * 0.5 * torch.sin(2 * math.pi * WF * ys + phase)

        # wiggle (oscillating wobble) on chosen axis
        WA = params["wiggle_amplitude"] * 2.0
        WFq = params["wiggle_frequency"]
        if params["wiggle_axis"] in ("horizontal", "both"):
            dx = dx + WA * torch.sin(2 * math.pi * WFq * ys + phase * 1.7)
        if params["wiggle_axis"] in ("vertical", "both"):
            dy = dy + WA * torch.sin(2 * math.pi * WFq * xs + phase * 1.3)

        # organic noise warp
        na = params["noise_amount"] * 2.0
        if na > 0:
            dx = dx + na * noise_x
            dy = dy + na * noise_y

        dx = dx * env
        dy = dy * env

        boundary = 0.12 * (dx + dy)  # the wipe edge follows the warp -> wiggly seam
        return dx, dy, boundary

    def _sweep_mask(self, H, W, p, direction, softness, boundary, dev, blk_thresh):
        """B-amount mask in [0,1]; sweeps fully 0 -> fully 1 as p goes 0 -> 1."""
        ys = torch.linspace(0.0, 1.0, H, device=dev).view(H, 1).expand(H, W)
        xs = torch.linspace(0.0, 1.0, W, device=dev).view(1, W).expand(H, W)
        if direction == "top_to_bottom":
            c = ys
        elif direction == "bottom_to_top":
            c = 1.0 - ys
        elif direction == "left_to_right":
            c = xs
        elif direction == "right_to_left":
            c = 1.0 - xs
        elif direction == "center_out":
            cx, cy = xs - 0.5, ys - 0.5
            c = torch.sqrt(cx * cx + cy * cy) / 0.7071
        elif direction == "random_blocks":
            c = (blk_thresh + 1.0) * 0.5  # 0..1 per block
        else:
            c = ys
        c = c + boundary
        pp = p * (1.0 + 2.0 * softness) - softness   # cover full range incl. soft edges
        m = torch.clamp((pp - c) / softness * 0.5 + 0.5, 0.0, 1.0)
        return m

    def _sample(self, img, base, dx, dy, edge_mode, ca):
        """grid_sample img[1,C,H,W] with per-channel chromatic offset."""
        pad = {"zeros": "zeros", "border": "border", "reflection": "reflection"}[edge_mode]
        C = img.shape[1]
        if ca <= 0 or C < 3:
            grid = torch.stack([base[..., 0] + dx, base[..., 1] + dy], dim=-1).unsqueeze(0)
            return F.grid_sample(img, grid, mode="bilinear", padding_mode=pad, align_corners=False)
        outs = []
        scales = [1.0 + ca, 1.0, 1.0 - ca]  # R, G, B split
        for ci in range(C):
            s = scales[ci] if ci < 3 else 1.0
            grid = torch.stack([base[..., 0] + dx * s, base[..., 1] + dy * s], dim=-1).unsqueeze(0)
            outs.append(F.grid_sample(img[:, ci:ci + 1], grid, mode="bilinear",
                                      padding_mode=pad, align_corners=False))
        return torch.cat(outs, dim=1)

    # ------------------------------------------------------------------
    def render(self, images_a, images_b, transition_frames, warp_pattern,
               warp_strength, warp_frequency, wiggle_amplitude, wiggle_frequency,
               wiggle_axis, block_size, noise_amount, sweep_direction,
               sweep_softness, easing, edge_mode, chromatic_aberration,
               parallax, seed):

        dev = images_a.device
        a = images_a.float()
        b = _match(a, images_b.float()).to(dev)

        N, H, W, C = a.shape
        Nb = b.shape[0]
        T = int(min(transition_frames, N, Nb))
        if T < 1:
            return (torch.cat([a, b], dim=0),)

        params = dict(warp_pattern=warp_pattern, warp_strength=warp_strength,
                      warp_frequency=warp_frequency, wiggle_amplitude=wiggle_amplitude,
                      wiggle_frequency=wiggle_frequency, wiggle_axis=wiggle_axis,
                      noise_amount=noise_amount)

        # static spatial fields (animation comes from env/phase + wiggle)
        nx = _value_noise(H, W, max(4, (H + W) // (2 * block_size)), seed, dev)
        ny = _value_noise(H, W, max(4, (H + W) // (2 * block_size)), seed + 101, dev)
        blkx = _block_noise(H, W, block_size, seed + 7, dev)
        blky = _block_noise(H, W, block_size, seed + 13, dev)
        blk_thresh = _block_noise(H, W, block_size, seed + 23, dev)

        ys = torch.linspace(-1.0, 1.0, H, device=dev).view(H, 1).expand(H, W)
        xs = torch.linspace(-1.0, 1.0, W, device=dev).view(1, W).expand(H, W)
        base = torch.stack([xs, ys], dim=-1)  # [H,W,2] (x,y)

        a_trans = a[N - T:]          # last T frames of A
        b_trans = b[:T]             # first T frames of B

        frames = []
        for i in range(T):
            p = _ease(i / max(1, (T - 1)), easing)
            dx, dy, boundary = self._displacement(H, W, p, params, dev, nx, ny, (blkx, blky))
            m = self._sweep_mask(H, W, p, sweep_direction, sweep_softness, boundary, dev, blk_thresh)

            ai = a_trans[i].permute(2, 0, 1).unsqueeze(0)
            bi = b_trans[i].permute(2, 0, 1).unsqueeze(0)
            # A pushed one way, B the other (parallax) so they don't move in lockstep
            wa = self._sample(ai, base, dx * (1.0 + parallax), dy * (1.0 + parallax),
                              edge_mode, chromatic_aberration)
            wb = self._sample(bi, base, dx * (1.0 - parallax), dy * (1.0 - parallax),
                              edge_mode, chromatic_aberration)
            mm = m.view(1, 1, H, W)
            out = wa * (1.0 - mm) + wb * mm
            frames.append(out.squeeze(0).permute(1, 2, 0))

        trans = torch.stack(frames, dim=0).clamp(0.0, 1.0)
        head = a[:N - T]
        tail = b[T:]
        result = torch.cat([head, trans, tail], dim=0)
        return (result,)
