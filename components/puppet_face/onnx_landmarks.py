"""
ComfyUI-PuppetFace  ·  ONNX landmark backend
============================================
Self-contained SCRFD (face detect) + 2d106det (106-point landmarks) using only
onnxruntime + cv2 + numpy.  NO insightface library, NO mediapipe, NO protobuf
bump -- so it can't break open-clip / CLIP in this portable.

Models are the antelopev2 pair already on disk:
  models/insightface/models/antelopev2/scrfd_10g_bnkps.onnx
  models/insightface/models/antelopev2/2d106det.onnx

NOTE (license): antelopev2 / insightface models are NON-COMMERCIAL.
Fine for testing + personal renders; swap for a permissive model before
shipping commercial output.

The math here mirrors insightface's own SCRFD / Landmark code (MIT), reduced to
the two model variants we actually have.
"""

import os
import numpy as np

_BACKEND = None        # cached (SCRFD, Landmark106) or False if unavailable


# ---------------------------------------------------------------------------
# model path resolution
# ---------------------------------------------------------------------------
def _antelope_dir():
    """Locate .../models/insightface/models/antelopev2 inside this ComfyUI."""
    candidates = []
    try:
        import folder_paths
        candidates.append(os.path.join(folder_paths.models_dir, "insightface",
                                       "models", "antelopev2"))
    except Exception:
        pass
    # walk up from this file: custom_nodes/msch-puppet-face/ -> ComfyUI/
    here = os.path.dirname(os.path.abspath(__file__))
    comfy_root = os.path.abspath(os.path.join(here, "..", ".."))
    candidates.append(os.path.join(comfy_root, "models", "insightface",
                                   "models", "antelopev2"))
    for d in candidates:
        if os.path.isfile(os.path.join(d, "2d106det.onnx")):
            return d
    return None


# ---------------------------------------------------------------------------
# insightface distance decoders
# ---------------------------------------------------------------------------
def _distance2bbox(points, distance):
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def _distance2kps(points, distance):
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


# ---------------------------------------------------------------------------
# SCRFD face detector (scrfd_10g_bnkps variant: fmc=3, anchors=2, kps)
# ---------------------------------------------------------------------------
class SCRFD:
    def __init__(self, model_path, input_size=(640, 640), conf=0.45, nms=0.4):
        import onnxruntime as ort
        ort.set_default_logger_severity(3)
        self.session = ort.InferenceSession(model_path,
                                            providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.conf = conf
        self.nms_thresh = nms
        self._feat_stride_fpn = [8, 16, 32]
        self.fmc = 3
        self._num_anchors = 2
        self.center_cache = {}

    def _forward(self, det_img, thresh):
        import cv2
        scores_list, bboxes_list = [], []
        blob = cv2.dnn.blobFromImage(
            det_img, 1.0 / 128.0, (det_img.shape[1], det_img.shape[0]),
            (127.5, 127.5, 127.5), swapRB=False)   # det_img already RGB
        outs = self.session.run(None, {self.input_name: blob})
        ih, iw = blob.shape[2], blob.shape[3]
        for idx, stride in enumerate(self._feat_stride_fpn):
            scores = outs[idx]
            bbox_preds = outs[idx + self.fmc] * stride
            h, w = ih // stride, iw // stride
            key = (h, w, stride)
            centers = self.center_cache.get(key)
            if centers is None:
                ac = np.stack(np.mgrid[:h, :w][::-1], axis=-1).astype(np.float32)
                ac = (ac * stride).reshape((-1, 2))
                if self._num_anchors > 1:
                    ac = np.stack([ac] * self._num_anchors, axis=1).reshape((-1, 2))
                centers = ac
                if len(self.center_cache) < 100:
                    self.center_cache[key] = ac
            pos = np.where(scores.ravel() >= thresh)[0]
            bboxes = _distance2bbox(centers, bbox_preds)
            scores_list.append(scores[pos])
            bboxes_list.append(bboxes[pos])
        return scores_list, bboxes_list

    def detect(self, img_rgb):
        """img_rgb: HxWx3 uint8 RGB. Returns largest bbox [x1,y1,x2,y2] or None."""
        import cv2
        h0, w0 = img_rgb.shape[:2]
        im_ratio = float(h0) / float(w0)
        model_ratio = float(self.input_size[1]) / float(self.input_size[0])
        if im_ratio > model_ratio:
            nh = self.input_size[1]
            nw = int(nh / im_ratio)
        else:
            nw = self.input_size[0]
            nh = int(nw * im_ratio)
        scale = float(nh) / h0
        resized = cv2.resize(img_rgb, (nw, nh))
        det_img = np.zeros((self.input_size[1], self.input_size[0], 3), dtype=np.uint8)
        det_img[:nh, :nw, :] = resized
        scores_list, bboxes_list = self._forward(det_img, self.conf)
        scores = np.vstack(scores_list).ravel()
        if scores.size == 0:
            return None
        bboxes = np.vstack(bboxes_list) / scale
        order = scores.argsort()[::-1]
        pre = np.hstack((bboxes, scores[:, None])).astype(np.float32)[order]
        keep = self._nms(pre)
        det = pre[keep]
        if det.shape[0] == 0:
            return None
        # largest area
        areas = (det[:, 2] - det[:, 0]) * (det[:, 3] - det[:, 1])
        return det[int(np.argmax(areas)), :4]

    def _nms(self, dets):
        x1, y1, x2, y2, s = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = s.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)
            order = order[np.where(ovr <= self.nms_thresh)[0] + 1]
        return keep


# ---------------------------------------------------------------------------
# 2d106det landmark regressor (input 192, output 212 = 106*2)
# ---------------------------------------------------------------------------
class Landmark106:
    def __init__(self, model_path):
        import onnxruntime as ort
        ort.set_default_logger_severity(3)
        self.session = ort.InferenceSession(model_path,
                                            providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.size = 192

    def get(self, img_rgb, bbox):
        import cv2
        x1, y1, x2, y2 = bbox[:4]
        w, h = (x2 - x1), (y2 - y1)
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        s = self.size / (max(w, h) * 1.5)
        # similarity transform (scale + translate, no rotation), insightface-style
        M = np.array([[s, 0, -s * cx + self.size / 2.0],
                      [0, s, -s * cy + self.size / 2.0]], dtype=np.float32)
        aimg = cv2.warpAffine(img_rgb, M, (self.size, self.size), borderValue=0.0)
        blob = cv2.dnn.blobFromImage(aimg, 1.0, (self.size, self.size),
                                     (0, 0, 0), swapRB=False)  # aimg already RGB
        pred = self.session.run(None, {self.input_name: blob})[0][0]  # (212,)
        pred = pred.reshape((-1, 2)).astype(np.float32)
        pred += 1.0
        pred *= (self.size // 2)
        IM = cv2.invertAffineTransform(M)
        ones = np.ones((pred.shape[0], 1), dtype=np.float32)
        pts = np.hstack([pred, ones]) @ IM.T  # (106,2) in original image px
        return pts


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def get_backend():
    """Return (SCRFD, Landmark106) or None. Cached; never raises."""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND or None
    try:
        d = _antelope_dir()
        if d is None:
            print("[PuppetFace] ONNX models not found (antelopev2); using fallback.")
            _BACKEND = False
            return None
        det = SCRFD(os.path.join(d, "scrfd_10g_bnkps.onnx"))
        lmk = Landmark106(os.path.join(d, "2d106det.onnx"))
        _BACKEND = (det, lmk)
        print("[PuppetFace] ONNX 106-pt tracker ready (SCRFD + 2d106det, CPU).")
        return _BACKEND
    except Exception as e:
        print(f"[PuppetFace] ONNX backend unavailable ({type(e).__name__}: {e}); "
              f"using fallback.")
        _BACKEND = False
        return None


def landmarks_106(pil):
    """PIL RGB -> np.ndarray (106,2) image-pixel landmarks, or None."""
    be = get_backend()
    if be is None:
        return None
    det, lmk = be
    img = np.asarray(pil.convert("RGB"))
    try:
        bbox = det.detect(img)
        if bbox is None:
            return None
        return lmk.get(img, bbox)
    except Exception as e:
        print(f"[PuppetFace] landmark inference failed ({type(e).__name__}: {e}).")
        return None


# ---------------------------------------------------------------------------
# geometric feature anchors (robust to exact 106 index semantics)
# ---------------------------------------------------------------------------
def feature_point(P, target):
    """Pick a cursor anchor from the 106-pt cloud P (np (106,2)). Always on-face."""
    cx, cy = P[:, 0].mean(), P[:, 1].mean()
    ymin, ymax = P[:, 1].min(), P[:, 1].max()
    fh = max(1.0, ymax - ymin)
    if target == "nose":
        # geometric center of a face mesh sits on the nose
        return P[int(np.argmin(((P[:, 0] - cx) ** 2 + (P[:, 1] - cy) ** 2)))]
    if target == "chin":
        return P[int(np.argmax(P[:, 1]))]
    if target == "mouth":
        band = P[P[:, 1] > cy + 0.10 * fh]
        if len(band) == 0:
            band = P
        sel = band[np.argsort(np.abs(band[:, 0] - cx))[:8]]
        return sel.mean(0)
    if target in ("eye_left", "eye_right"):
        upper = P[P[:, 1] < cy - 0.04 * fh]
        if len(upper) == 0:
            upper = P
        side = upper[upper[:, 0] < cx] if target == "eye_left" else upper[upper[:, 0] > cx]
        if len(side) == 0:
            side = upper
        return side.mean(0)
    return np.array([cx, cy], dtype=np.float32)
