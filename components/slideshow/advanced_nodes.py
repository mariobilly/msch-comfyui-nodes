import json
import math
import uuid
from pathlib import Path

import av
import numpy as np
import torch
from PIL import Image, ImageDraw

import folder_paths
from comfy.model_management import throw_exception_if_processing_interrupted
from comfy.utils import ProgressBar

from .analysis_tools import analyze_beats, detect_focus, focus_preview
from .engine import open_photo
from .nodes import MarioSlideshow, TensorPhotos, file_fingerprint, image_files, image_tensor
from .planning import PRESETS, build_plan, validate_focus, validate_plan


def resolve_file(value):
    path = Path(value.strip()).expanduser()
    if not path.is_absolute():
        path = Path(folder_paths.get_input_directory()) / path
    if not path.is_file():
        raise ValueError(f"File does not exist: {path}")
    return path


def preview_result(image, result):
    directory = Path(folder_paths.get_temp_directory())
    directory.mkdir(parents=True, exist_ok=True)
    name = f"mario_analysis_{uuid.uuid4().hex[:12]}.png"
    image.save(directory / name)
    return {"ui": {"images": [{"filename": name, "subfolder": "", "type": "temp"}]}, "result": result}


class MarioBeatAnalyzer:
    CATEGORY = "marioslideshow/advanced"
    FUNCTION = "analyze"
    RETURN_TYPES = ("MARIO_BEATS", "FLOAT", "IMAGE", "STRING")
    RETURN_NAMES = ("beats", "bpm", "beat_preview", "beat_json")
    DESCRIPTION = "Detect actual music beats. Connect the same soundtrack separately to the renderer."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "audio_file": ("STRING", {"default": "", "tooltip": "Leave empty when AUDIO is connected."}),
            "tempo_hint": ("FLOAT", {"default": 0.0, "min": 0, "max": 300, "step": 1,
                                    "tooltip": "0 estimates tempo. Set BPM to correct half/double-tempo detection."}),
            "beat_offset_seconds": ("FLOAT", {"default": 0.0, "min": -1, "max": 1, "step": 0.01}),
            "max_seconds": ("FLOAT", {"default": 180.0, "min": 2, "max": 600, "step": 1}),
        }, "optional": {"audio": ("AUDIO",)}}

    @classmethod
    def IS_CHANGED(cls, audio_file="", **kwargs):
        return file_fingerprint([resolve_file(audio_file)]) if audio_file.strip() else "audio_input"

    def analyze(self, audio_file, tempo_hint, beat_offset_seconds, max_seconds, audio=None):
        if (audio is not None) == bool(audio_file.strip()):
            raise ValueError("Provide either an AUDIO input or audio_file.")
        if not 2 <= max_seconds <= 600 or not -1 <= beat_offset_seconds <= 1 or not (tempo_hint == 0 or 20 <= tempo_hint <= 300):
            raise ValueError("Use 2-600 seconds, an offset from -1 to 1, and tempo_hint 0 or 20-300 BPM.")
        if audio is not None:
            waveform, rate = audio["waveform"], int(audio["sample_rate"])
            if waveform.ndim != 3 or waveform.shape[0] != 1 or waveform.shape[1] not in (1, 2) or not 8000 <= rate <= 192000:
                raise ValueError("AUDIO must be one mono/stereo waveform at 8000-192000 Hz.")
            mono = waveform[0, :, :math.ceil(max_seconds * rate)].detach().to(device="cpu", dtype=torch.float32).mean(dim=0).numpy()
        else:
            rate = 22050
            chunks, count = [], 0
            with av.open(str(resolve_file(audio_file))) as container:
                if not container.streams.audio:
                    raise ValueError("The file contains no audio stream.")
                resampler = av.AudioResampler(format="fltp", layout="mono", rate=rate)
                for frame in container.decode(audio=0):
                    throw_exception_if_processing_interrupted()
                    for resampled in resampler.resample(frame):
                        chunk = resampled.to_ndarray().reshape(-1)
                        chunks.append(chunk)
                        count += len(chunk)
                    if count >= max_seconds * rate:
                        break
                for frame in resampler.resample(None):
                    chunks.append(frame.to_ndarray().reshape(-1))
            if not chunks:
                raise ValueError("No audio samples could be decoded.")
            mono = np.concatenate(chunks)[:math.ceil(max_seconds * rate)]
        beats, preview = analyze_beats(mono, rate, tempo_hint, beat_offset_seconds, throw_exception_if_processing_interrupted)
        return preview_result(preview, (beats, beats["bpm"], image_tensor(preview), json.dumps(beats, indent=2)))


class MarioSubjectFramer:
    CATEGORY = "marioslideshow/advanced"
    FUNCTION = "analyze"
    RETURN_TYPES = ("MARIO_FOCUS", "IMAGE", "STRING")
    RETURN_NAMES = ("focus", "framing_preview", "focus_json")
    DESCRIPTION = "Face or mask-guided framing. Connect the same source photos to this node and the renderer."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "mode": (["Faces", "Manual"],),
            "subject_margin": ("FLOAT", {"default": 0.20, "min": 0, "max": 1, "step": 0.05}),
            "focus_x": ("FLOAT", {"default": 0.5, "min": 0, "max": 1, "step": 0.01}),
            "focus_y": ("FLOAT", {"default": 0.5, "min": 0, "max": 1, "step": 0.01}),
            "overrides_json": ("STRING", {"default": "", "multiline": True,
                "tooltip": "Optional zero-based image overrides, e.g. {\"0\": {\"x\": 0.8, \"y\": 0.3}}. Coordinates are normalized."}),
        }, "optional": {"photos": ("MARIO_IMAGES",), "images": ("IMAGE",), "masks": ("MASK",)}}

    def analyze(self, mode, subject_margin, focus_x, focus_y, overrides_json, photos=None, images=None, masks=None):
        if (photos is not None) == (images is not None):
            raise ValueError("Connect either photos or images to Subject Framer.")
        if mode not in ("Faces", "Manual") or not 0 <= subject_margin <= 1 or not 0 <= focus_x <= 1 or not 0 <= focus_y <= 1:
            raise ValueError("Invalid framing mode, margin or focus coordinates.")
        source = photos["paths"] if photos is not None else TensorPhotos(images)
        if not 1 <= len(source) <= 200:
            raise ValueError("Subject Framer supports 1-200 source images.")
        if masks is not None and (masks.ndim != 3 or masks.shape[0] != len(source)):
            raise ValueError("Provide one subject mask per source image, as [B, H, W].")
        overrides = json.loads(overrides_json) if overrides_json.strip() else {}
        if not isinstance(overrides, dict) or any(not k.isdigit() or str(int(k)) != k or not 0 <= int(k) < len(source) for k in overrides):
            raise ValueError("Override keys must be zero-based source image indices.")
        detector = None
        if mode == "Faces" and masks is None:
            from skimage import data
            from skimage.feature import Cascade
            detector = Cascade(data.lbp_frontal_face_cascade_filename())
        columns = min(4, len(source))
        sheet = Image.new("RGB", (columns * 336, math.ceil(min(12, len(source)) / columns) * 296), (22, 24, 25))
        items = []
        progress = ProgressBar(len(source))
        for index in range(len(source)):
            throw_exception_if_processing_interrupted()
            image = open_photo(source[index])
            mask = masks[index].detach().to(device="cpu", dtype=torch.float32).numpy() if masks is not None else None
            if mask is not None and not np.isfinite(mask).all():
                raise ValueError("Subject masks must contain finite values.")
            item = detect_focus(image, mode, focus_x, focus_y, subject_margin, mask, detector)
            override = overrides.get(str(index))
            if override is not None:
                if not isinstance(override, dict) or set(override) - {"x", "y", "box"}:
                    raise ValueError("Overrides may contain only x, y and box.")
                item.update(override)
                item["method"] = "override"
                if "box" not in override:
                    x, y = item["x"], item["y"]
                    if type(x) not in (int, float) or type(y) not in (int, float):
                        raise ValueError("Override x and y must be numbers.")
                    item["box"] = [max(0, x - 0.025), max(0, y - 0.025), min(1, x + 0.025), min(1, y + 0.025)]
            validate_focus({"version": 1, "items": [item]}, 1)
            items.append(item)
            if index < 12:
                preview = focus_preview(image, item)
                x, y = (index % columns) * 336, (index // columns) * 296
                sheet.paste(preview, (x + (336 - preview.width) // 2, y + 4))
                ImageDraw.Draw(sheet).text((x + 8, y + 272), f"IMAGE {index} / {item['method']}", fill=(232, 235, 230))
            progress.update(1)
        focus = {"version": 1, "items": items}
        return preview_result(sheet, (focus, image_tensor(sheet), json.dumps(focus, indent=2)))


class MarioSlideshowDirector:
    CATEGORY = "marioslideshow/advanced"
    FUNCTION = "direct"
    RETURN_TYPES = ("MARIO_PLAN", "STRING", "IMAGE", "FLOAT")
    RETURN_NAMES = ("plan", "timeline_json", "timeline_preview", "duration_seconds")
    DESCRIPTION = "Plan scenes, transitions, source order and shot timing without rendering a video."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image_count": ("INT", {"default": 8, "min": 1, "max": 200}),
            "preset": (list(PRESETS),),
            "timing": (["BPM", "Seconds"],),
            "bpm": ("FLOAT", {"default": 128.0, "min": 20, "max": 300, "step": 1}),
            "beats_per_image": ("FLOAT", {"default": 4.0, "min": 1, "max": 16, "step": 0.5}),
            "seconds_per_image": ("FLOAT", {"default": 2.0, "min": 0.4, "max": 30, "step": 0.1}),
            "pacing": (["Dynamic", "Even"],),
            "headlines": ("STRING", {"default": "", "multiline": True}),
            "shuffle": ("BOOLEAN", {"default": False}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
            "timeline_json_in": ("STRING", {"default": "", "multiline": True,
                "tooltip": "Paste edited timeline_json here. It replaces the generated plan, including timing and headlines."}),
        }, "optional": {"beats": ("MARIO_BEATS",)}}

    def direct(self, image_count, preset, timing, bpm, beats_per_image, seconds_per_image, pacing,
               headlines, shuffle, seed, timeline_json_in, beats=None):
        plan = json.loads(timeline_json_in) if timeline_json_in.strip() else build_plan(
            image_count, preset, timing, bpm, beats_per_image, seconds_per_image, pacing, headlines, shuffle, seed, beats)
        plan = validate_plan(plan, image_count)
        duration = sum(s["duration"] for s in plan["shots"])
        rows = math.ceil(len(plan["shots"]) / 6)
        chart = Image.new("RGB", (1200, rows * 98 + 42), (22, 24, 25))
        draw = ImageDraw.Draw(chart)
        draw.text((20, 12), f"SHOT PLAN / {len(plan['shots'])} shots / {duration:.2f}s / {plan.get('timing_source', 'edited')}", fill=(235, 237, 233))
        start = 0.0
        colors = {"hero": (65, 95, 119), "split": (98, 111, 63), "stack": (129, 76, 90),
                  "triptych": (95, 81, 119), "gallery": (117, 110, 82),
                  "window": (56, 93, 93), "mosaic": (133, 78, 48)}
        for index, shot in enumerate(plan["shots"]):
            x, y = (index % 6) * 200 + 12, (index // 6) * 98 + 40
            draw.rectangle((x, y, x + 184, y + 82), fill=colors[shot["scene"]])
            draw.text((x + 8, y + 7), f"SHOT {index + 1:02d} / IMAGE {shot['image_index']}", fill="white")
            draw.text((x + 8, y + 29), f"{start:.2f}s + {shot['duration']:.2f}s", fill="white")
            draw.text((x + 8, y + 53), f"{shot['scene']} / {shot['transition']}", fill="white")
            start += shot["duration"]
        text = json.dumps(plan, indent=2)
        result = preview_result(chart, (plan, text, image_tensor(chart), duration))
        result["ui"]["mario_plan_json"] = [text]
        return result


class MarioSlideshowRenderer(MarioSlideshow):
    CATEGORY = "marioslideshow/advanced"
    FUNCTION = "render_plan"
    DESCRIPTION = "Render a Director plan with optional subject framing and audio, streaming directly to MP4."

    @classmethod
    def INPUT_TYPES(cls):
        base = MarioSlideshow.INPUT_TYPES()
        keep = ("image_folder", "width", "height", "fps", "framing", "transition_seconds", "intensity",
                "motion_blur", "grain", "accent", "graphics", "font_path", "audio_file", "quality", "seed", "filename_prefix")
        return {"required": {"plan": ("MARIO_PLAN",), **{name: base["required"][name] for name in keep}},
                "optional": {name: base["optional"][name] for name in ("photos", "images", "audio", "focus",
                    "show_counter", "show_progress", "show_headlines", "headline_layers")},
                "hidden": base["hidden"]}

    def render_plan(self, plan, photos=None, images=None, audio=None, focus=None, prompt=None, extra_pnginfo=None, **kwargs):
        defaults = {}
        for name, definition in MarioSlideshow.INPUT_TYPES()["required"].items():
            options = definition[1] if len(definition) > 1 else {}
            defaults[name] = options["default"] if "default" in options else definition[0][0]
        defaults.update(kwargs)
        return self.render(**defaults, plan=plan, photos=photos, images=images, audio=audio,
                           focus=focus, prompt=prompt, extra_pnginfo=extra_pnginfo)


ADVANCED_NODE_CLASS_MAPPINGS = {"MarioBeatAnalyzer": MarioBeatAnalyzer, "MarioSubjectFramer": MarioSubjectFramer,
    "MarioSlideshowDirector": MarioSlideshowDirector, "MarioSlideshowRenderer": MarioSlideshowRenderer}
ADVANCED_NODE_DISPLAY_NAME_MAPPINGS = {"MarioBeatAnalyzer": "marioslideshow - Beat Analyzer",
    "MarioSubjectFramer": "marioslideshow - Subject Framer", "MarioSlideshowDirector": "marioslideshow - Director",
    "MarioSlideshowRenderer": "marioslideshow - Renderer"}
