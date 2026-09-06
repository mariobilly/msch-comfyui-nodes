"""
ComfyUI-PuppetFace
==================
The signature "point-and-click" puppet look: draw a tracking landmark mesh
and an animated mouse cursor over a batch of face frames.

Pipeline role:
  GPT Image 2.0 (portrait)  ->  LivePortrait / Wan 2.2 (expression frames)
  ->  [ PuppetFace Landmark + Cursor Overlay ]  ->  final reel

The node ALWAYS loads. Landmark source priority:
  1. ONNX 106-pt tracker (SCRFD + 2d106det via onnxruntime) -- preferred,
     sticks to the deforming face, no protobuf/mediapipe risk. See onnx_landmarks.py.
  2. mediapipe FaceMesh (478 pts) -- only if ONNX models are absent.
  3. cv2-Haar parametric oval -- zero-dep last resort.
The cursor anchors to a geometric feature (nose/mouth/eye/chin) so it lands
ON the face instead of guessing.
"""

import numpy as np
import torch
from PIL import Image, ImageDraw

# ONNX 106-pt tracker (SCRFD + 2d106det). Robust, zero protobuf risk, CPU.
# Preferred over the cv2-Haar oval fallback. Loads lazily; safe if unavailable.
try:
    from . import onnx_landmarks as _ol
except Exception:
    try:
        import onnx_landmarks as _ol
    except Exception:
        _ol = None

# ----------------------------------------------------------------------------
# Optional mediapipe FaceMesh (lazy, cached). Missing -> graceful fallback.
# ----------------------------------------------------------------------------
_FACEMESH = None
_MP_OK = None  # tri-state: None=untried, True/False=result


def _get_facemesh():
    global _FACEMESH, _MP_OK
    if _MP_OK is False:
        return None
    if _FACEMESH is not None:
        return _FACEMESH
    try:
        import mediapipe as mp
        _FACEMESH = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,      # each frame is an independent expression
            max_num_faces=1,
            refine_landmarks=True,        # 478 pts incl. irises
            min_detection_confidence=0.35,
        )
        _MP_OK = True
        print("[PuppetFace] mediapipe FaceMesh ready (real landmark tracking).")
    except Exception as e:
        _MP_OK = False
        print(f"[PuppetFace] mediapipe not available ({type(e).__name__}); "
              f"using parametric fallback dots. `pip install mediapipe` for tracking.")
    return _FACEMESH


# Landmark index groups (mediapipe FaceMesh). Built lazily so import never fails.
def _mp_index_sets():
    import mediapipe as mp
    fm = mp.solutions.face_mesh
    def idx(conn):
        s = set()
        for a, b in conn:
            s.add(a); s.add(b)
        return s
    contours = idx(fm.FACEMESH_CONTOURS)
    tess = idx(fm.FACEMESH_TESSELATION)
    key = idx(fm.FACEMESH_CONTOURS) | idx(fm.FACEMESH_IRISES)
    return {
        "key": sorted(key),
        "contours": sorted(contours),
        "tesselation": sorted(tess),
        "all": list(range(478)),
        "_connections": fm.FACEMESH_CONTOURS,
    }


# ----------------------------------------------------------------------------
# cv2 Haar face box (zero-dep fallback so the mesh/cursor snap to the real face)
# ----------------------------------------------------------------------------
_HAAR = None


def _get_haar():
    global _HAAR
    if _HAAR is None:
        import cv2, os
        p = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        _HAAR = cv2.CascadeClassifier(p)
    return _HAAR


def _detect_face_box(pil):
    """Largest frontal-face box (x, y, w, h) or None."""
    try:
        import cv2
        g = cv2.cvtColor(np.asarray(pil.convert("RGB")), cv2.COLOR_RGB2GRAY)
        faces = _get_haar().detectMultiScale(g, scaleFactor=1.12, minNeighbors=5,
                                             minSize=(50, 50))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return (int(x), int(y), int(w), int(h))
    except Exception:
        return None


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def _hex_to_rgb(s, default=(255, 255, 255)):
    try:
        s = s.strip().lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return default


def _tensor_to_pils(image):
    arr = (image.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)  # [B,H,W,C]
    return [Image.fromarray(a, "RGB") for a in arr]


def _pils_to_tensor(pils):
    arr = np.stack([np.asarray(p.convert("RGB"), dtype=np.float32) / 255.0 for p in pils], 0)
    return torch.from_numpy(arr)


# classic arrow cursor polygon, tip at (0,0), pointing up-left, ~ unit/16 scale
_CURSOR_POLY = [
    (0, 0), (0, 17), (4.2, 13.2), (7.0, 19.5),
    (9.6, 18.3), (6.8, 12.2), (12.0, 12.0),
]


def _draw_cursor(draw, x, y, scale, fill, outline):
    pts = [(x + px * scale, y + py * scale) for px, py in _CURSOR_POLY]
    draw.polygon(pts, fill=fill, outline=outline)
    # thin double outline for the crisp OS-cursor edge
    draw.line(pts + [pts[0]], fill=outline, width=max(1, int(scale)))


def _lerp(a, b, t):
    return a + (b - a) * t


# ----------------------------------------------------------------------------
# node
# ----------------------------------------------------------------------------
class PuppetFaceOverlay:
    """Landmark + animated cursor overlay (the 'point and click' signature)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "show_dots": ("BOOLEAN", {"default": True}),
                "dot_set": (["key", "contours", "tesselation", "all"], {"default": "key"}),
                "dot_radius": ("INT", {"default": 2, "min": 1, "max": 20}),
                "dot_color": ("STRING", {"default": "#FFFFFF"}),
                "dot_opacity": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.05}),
                "show_mesh": ("BOOLEAN", {"default": False}),
                "mesh_opacity": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 1.0, "step": 0.05}),
                "cursor_mode": (["track_landmark", "sweep", "off"], {"default": "track_landmark"}),
                "cursor_scale": ("FLOAT", {"default": 1.6, "min": 0.3, "max": 8.0, "step": 0.1}),
                "cursor_landmark": ("INT", {"default": 14, "min": 0, "max": 477}),
                "grab_ring": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                # appended last so existing saved workflows keep widget alignment
                "cursor_target": (["nose", "mouth", "eye_left", "eye_right", "chin",
                                   "landmark_index"], {"default": "nose"}),
                "sweep_start_x": ("FLOAT", {"default": 0.15, "min": 0.0, "max": 1.0, "step": 0.01}),
                "sweep_start_y": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.01}),
                "sweep_end_x": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "sweep_end_y": ("FLOAT", {"default": 0.55, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "apply"
    CATEGORY = "PuppetFace"

    # -- landmark sourcing -------------------------------------------------
    def _landmarks_for_frame(self, pil, fm):
        """Return list[(x_px,y_px)] for this frame, or None."""
        if fm is None:
            return None
        rgb = np.asarray(pil.convert("RGB"))
        res = fm.process(rgb)
        if not res.multi_face_landmarks:
            return None
        w, h = pil.size
        lm = res.multi_face_landmarks[0].landmark
        return [(p.x * w, p.y * h) for p in lm]

    def _fallback_oval(self, w, h, n=120, box=None):
        """Parametric dot oval when no FaceMesh. If a cv2 face box is given the
        mesh snaps to the real face position/scale (tracks the head per frame)."""
        if box is not None:
            bx, by, bw, bh = box
            cx, cy = bx + bw * 0.5, by + bh * 0.52
            rx, ry = bw * 0.62, bh * 0.70
        else:
            cx, cy, rx, ry = w * 0.5, h * 0.5, w * 0.30, h * 0.38
        pts = []
        for i in range(n):
            t = 2 * np.pi * i / n
            pts.append((cx + rx * np.cos(t), cy + ry * np.sin(t)))
        # inner clusters (eyes/mouth), scaled to the oval so they sit on the face
        for (ox, oy, er) in [(-0.40, -0.28, 0.16), (0.40, -0.28, 0.16), (0.0, 0.46, 0.30)]:
            for i in range(18):
                t = 2 * np.pi * i / 18
                pts.append((cx + ox * rx + er * rx * np.cos(t),
                            cy + oy * ry + er * ry * np.sin(t)))
        return pts

    def apply(self, images, show_dots, dot_set, dot_radius, dot_color, dot_opacity,
              show_mesh, mesh_opacity, cursor_mode, cursor_scale, cursor_landmark,
              grab_ring, cursor_target="nose", sweep_start_x=0.15, sweep_start_y=0.85,
              sweep_end_x=0.5, sweep_end_y=0.55):

        pils = _tensor_to_pils(images)
        n = len(pils)
        need_lm = (show_dots or show_mesh or cursor_mode == "track_landmark")
        # ONNX 106-pt tracker is the preferred source (sticks to the deforming
        # face). mediapipe is used only if ONNX is unavailable; cv2-Haar oval last.
        use_onnx = bool(need_lm and _ol is not None and _ol.get_backend() is not None)
        fm = _get_facemesh() if (need_lm and not use_onnx) else None

        dot_rgb = _hex_to_rgb(dot_color)
        idx_sets = None
        connections = None
        if fm is not None and (show_dots or show_mesh):
            try:
                idx_sets = _mp_index_sets()
                connections = idx_sets["_connections"]
            except Exception:
                idx_sets = None

        out = []
        last_cursor = None
        last_onnx = None   # temporal hold: carry last good 106-pts over a dropped frame
        for i, pil in enumerate(pils):
            w, h = pil.size
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(overlay)

            # ---- landmark sourcing: ONNX 106 > mediapipe 478 > Haar oval ----
            onnx_pts = _ol.landmarks_106(pil) if use_onnx else None  # np (106,2) or None
            if onnx_pts is not None:
                last_onnx = onnx_pts
            elif use_onnx and last_onnx is not None:
                onnx_pts = last_onnx          # hold last good frame, skip ugly oval pop
            lms = None if onnx_pts is not None else (
                self._landmarks_for_frame(pil, fm) if fm is not None else None)
            box = None
            if onnx_pts is None and lms is None and need_lm:
                box = _detect_face_box(pil)
            draw_pts = lms if lms is not None else (
                self._fallback_oval(w, h, box=box) if (show_dots or show_mesh) else None)

            # mesh lines (only with mediapipe topology)
            if show_mesh and lms is not None and connections is not None and mesh_opacity > 0:
                a = int(255 * mesh_opacity)
                for (s, e) in connections:
                    if s < len(lms) and e < len(lms):
                        d.line([lms[s], lms[e]], fill=(*dot_rgb, a), width=1)

            # dots
            if show_dots and dot_opacity > 0:
                a = int(255 * dot_opacity)
                if onnx_pts is not None:
                    pts = onnx_pts[::2] if dot_set == "key" else onnx_pts
                elif lms is not None and idx_sets is not None:
                    sel = idx_sets.get(dot_set, idx_sets["key"])
                    pts = [lms[j] for j in sel if j < len(lms)]
                else:
                    pts = draw_pts
                if pts is not None:
                    r = dot_radius
                    for (x, y) in pts:
                        d.ellipse([x - r, y - r, x + r, y + r], fill=(*dot_rgb, a))

            # cursor position
            cpos = None
            if cursor_mode == "track_landmark":
                if onnx_pts is not None:
                    # geometric feature anchor (robust); index mode for power users
                    if cursor_target == "landmark_index":
                        cpos = tuple(onnx_pts[min(cursor_landmark, len(onnx_pts) - 1)])
                    else:
                        cpos = tuple(_ol.feature_point(onnx_pts, cursor_target))
                elif lms is not None and cursor_landmark < len(lms):
                    cpos = lms[cursor_landmark]
                elif box is not None:
                    # no landmarks: anchor cursor to the mouth region of the face box
                    bx, by, bw, bh = box
                    cpos = (bx + bw * 0.5, by + bh * 0.78)
                elif last_cursor is not None:
                    cpos = last_cursor
                else:
                    cpos = (sweep_end_x * w, sweep_end_y * h)
            elif cursor_mode == "sweep":
                t = 0.0 if n <= 1 else i / (n - 1)
                cpos = (_lerp(sweep_start_x, sweep_end_x, t) * w,
                        _lerp(sweep_start_y, sweep_end_y, t) * h)

            if cpos is not None:
                last_cursor = cpos
                cx, cy = cpos
                if grab_ring:
                    rr = 9 * cursor_scale
                    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                              outline=(255, 255, 255, 150), width=max(1, int(cursor_scale)))
                _draw_cursor(d, cx, cy, cursor_scale * 1.6,
                             fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))

            base = pil.convert("RGBA")
            base.alpha_composite(overlay)
            out.append(base.convert("RGB"))

        return (_pils_to_tensor(out),)


# ----------------------------------------------------------------------------
# Self-contained video I/O (cv2) so the video workflow needs no other packs
# ----------------------------------------------------------------------------
def _comfy_dir(kind):
    try:
        import folder_paths
        return (folder_paths.get_input_directory() if kind == "input"
                else folder_paths.get_output_directory())
    except Exception:
        return "."


def _even(x):
    x = int(round(x))
    return x - (x % 2)


class PuppetFaceLoadVideo:
    """Read an mp4/mov into an IMAGE batch (+ fps). Path is relative to the
    ComfyUI input/ folder unless absolute."""

    VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".gif", ".m4v")

    @classmethod
    def _list_input_videos(cls):
        import os
        try:
            d = _comfy_dir("input")
            vids = sorted(f for f in os.listdir(d) if f.lower().endswith(cls.VIDEO_EXTS))
        except Exception:
            vids = []
        return vids or ["(drop a video in input/ then refresh)"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": (cls._list_input_videos(),),
                "frame_load_cap": ("INT", {"default": 0, "min": 0, "max": 100000}),
                "select_every_nth": ("INT", {"default": 1, "min": 1, "max": 100}),
                "max_side": ("INT", {"default": 0, "min": 0, "max": 4096,
                                     "tooltip": "0 = keep original; else resize longest side"}),
            },
            "optional": {
                "path_override": ("STRING", {"default": "",
                    "tooltip": "Full path to ANY video; if set, overrides the dropdown."}),
            },
        }

    # re-scan input/ each run so newly added files are seen
    @classmethod
    def IS_CHANGED(cls, video, frame_load_cap, select_every_nth, max_side, path_override=""):
        import os
        src = (path_override or "").strip().strip('"').strip("'") or video
        p = src if os.path.isabs(src) else os.path.join(_comfy_dir("input"), src)
        try:
            return os.path.getmtime(p)
        except Exception:
            return src

    RETURN_TYPES = ("IMAGE", "FLOAT", "INT")
    RETURN_NAMES = ("images", "fps", "frame_count")
    FUNCTION = "load"
    CATEGORY = "PuppetFace"

    def load(self, video, frame_load_cap, select_every_nth, max_side, path_override=""):
        import os, cv2
        # path_override (if given) wins; tolerate "Copy as path" quotes + whitespace
        src = (path_override or "").strip().strip('"').strip("'").strip() or video
        path = src if os.path.isabs(src) else os.path.join(_comfy_dir("input"), src)
        if not os.path.exists(path):
            raise FileNotFoundError(f"[PuppetFace] video not found: {path}")
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        frames, i = [], 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            if i % select_every_nth == 0:
                rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
                if max_side > 0:
                    h, w = rgb.shape[:2]
                    s = max_side / float(max(h, w))
                    if s < 1.0:
                        rgb = cv2.resize(rgb, (_even(w * s), _even(h * s)),
                                         interpolation=cv2.INTER_AREA)
                frames.append(rgb)
                if frame_load_cap and len(frames) >= frame_load_cap:
                    break
            i += 1
        cap.release()
        if not frames:
            raise RuntimeError(f"[PuppetFace] no frames decoded from {path}")
        arr = np.stack(frames).astype(np.float32) / 255.0
        eff_fps = float(fps) / float(select_every_nth)
        print(f"[PuppetFace] loaded {len(frames)} frames @ {eff_fps:.2f} fps from {os.path.basename(path)}")
        return (torch.from_numpy(arr), eff_fps, len(frames))


class PuppetFaceSaveVideo:
    """Write an IMAGE batch to an .mp4 in the ComfyUI output/ folder."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "forceInput": True}),
                "filename_prefix": ("STRING", {"default": "PuppetFace"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "PuppetFace"

    def save(self, images, fps, filename_prefix):
        import os, cv2
        out_dir = _comfy_dir("output")
        os.makedirs(out_dir, exist_ok=True)
        # unique filename
        n = 0
        while True:
            name = f"{filename_prefix}_{n:05d}.mp4"
            path = os.path.join(out_dir, name)
            if not os.path.exists(path):
                break
            n += 1

        arr = (images.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)  # [B,H,W,3] RGB
        h, w = arr.shape[1:3]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        vw = cv2.VideoWriter(path, fourcc, max(1.0, float(fps)), (w, h))
        if not vw.isOpened():
            raise RuntimeError("[PuppetFace] cv2.VideoWriter failed to open (codec issue)")
        for fr in arr:
            vw.write(cv2.cvtColor(fr, cv2.COLOR_RGB2BGR))
        vw.release()
        print(f"[PuppetFace] saved {arr.shape[0]} frames -> {path}")
        return {"ui": {"text": [name]}, "result": (path,)}


NODE_CLASS_MAPPINGS = {
    "PuppetFaceOverlay": PuppetFaceOverlay,
    "PuppetFaceLoadVideo": PuppetFaceLoadVideo,
    "PuppetFaceSaveVideo": PuppetFaceSaveVideo,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PuppetFaceOverlay": "PuppetFace ▸ Landmark + Cursor Overlay",
    "PuppetFaceLoadVideo": "PuppetFace ▸ Load Video",
    "PuppetFaceSaveVideo": "PuppetFace ▸ Save Video",
}
