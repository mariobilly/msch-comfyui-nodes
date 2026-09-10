from __future__ import annotations

import hashlib
import json
import math
import re
import tempfile
import uuid
import wave
from dataclasses import asdict
from pathlib import Path

import av
import numpy as np
import torch
from PIL import Image, ImageOps

import folder_paths
from comfy.model_management import throw_exception_if_processing_interrupted
from comfy.utils import ProgressBar
from comfy_api.input_impl import VideoFromFile

from .engine import PromoRenderer, Settings, VideoWriter, open_photo
from .planning import build_plan, validate_focus
from .._paths import input_path, output_path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def natural_key(path):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def image_files(directory, max_images=200, order="Natural"):
    if not directory.strip():
        raise ValueError("Upload images, enter an image folder, or connect an IMAGE batch.")
    path = input_path(directory, kind="directory")
    if order not in ("Natural", "Newest first"):
        raise ValueError("Unknown image order.")
    files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    # Validate individual entries too: an in-bounds directory can contain links.
    base = Path(folder_paths.get_input_directory()).resolve()
    files = [input_path(p.relative_to(base).as_posix()) for p in files]
    files.sort(key=natural_key if order == "Natural" else lambda p: -p.stat().st_mtime_ns)
    files = files[:max(1, min(200, int(max_images)))]
    if not files:
        raise ValueError("No PNG, JPEG, WebP, BMP, or TIFF images found in that folder.")
    return files


def file_fingerprint(paths):
    digest = hashlib.sha256()
    for path in paths:
        stat = path.stat()
        digest.update(f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


def image_tensor(image):
    return torch.from_numpy(np.array(image.convert("RGB"), dtype=np.float32) / 255.0).unsqueeze(0)


class TensorPhotos:
    def __init__(self, tensor):
        if tensor.ndim != 4 or tensor.shape[-1] not in (3, 4):
            raise ValueError("images must be a ComfyUI IMAGE batch [B, H, W, 3 or 4].")
        self.tensor = tensor

    def __len__(self):
        return self.tensor.shape[0]

    def __getitem__(self, index):
        array = self.tensor[index].detach().to(device="cpu", dtype=torch.float32).numpy()
        return Image.fromarray(np.clip(array * 255, 0, 255).astype(np.uint8))


class OrderedPhotos:
    def __init__(self, photos, order):
        self.photos, self.order = photos, order

    def __len__(self):
        return len(self.order)

    def __getitem__(self, index):
        return self.photos[self.order[index]]


class MarioSlideshowLoadImages:
    CATEGORY = "marioslideshow"
    FUNCTION = "load"
    RETURN_TYPES = ("MARIO_IMAGES", "IMAGE", "INT")
    RETURN_NAMES = ("photos", "contact_sheet", "image_count")
    DESCRIPTION = "Upload multiple photos or load a folder. Preserves each photo's original aspect ratio."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "directory": ("STRING", {"default": "", "tooltip": "Folder relative to ComfyUI/input. Absolute paths and '..' are rejected."}),
            "max_images": ("INT", {"default": 100, "min": 1, "max": 200}),
            "order": (["Natural", "Newest first"],),
        }}

    @classmethod
    def IS_CHANGED(cls, directory, max_images, order):
        return file_fingerprint(image_files(directory, max_images, order))

    def load(self, directory, max_images, order):
        files = image_files(directory, max_images, order)
        count = min(12, len(files))
        columns = min(4, count)
        sheet = Image.new("RGB", (columns * 256, math.ceil(count / columns) * 192), (18, 18, 20))
        for index, path in enumerate(files[:count]):
            throw_exception_if_processing_interrupted()
            thumb = ImageOps.contain(open_photo(path), (248, 184), Image.Resampling.LANCZOS)
            x, y = index % columns * 256, index // columns * 192
            sheet.paste(thumb, (x + (256 - thumb.width) // 2, y + (192 - thumb.height) // 2))
        return ({"paths": files}, image_tensor(sheet), len(files))


class MarioSlideshow:
    CATEGORY = "marioslideshow"
    FUNCTION = "render"
    OUTPUT_NODE = True
    RETURN_TYPES = ("VIDEO", "STRING", "IMAGE", "FLOAT", "INT")
    RETURN_NAMES = ("video", "mp4_path", "poster", "fps", "frame_count")
    DESCRIPTION = "High-energy photo promo with layered scenes, motion blur, beat-grid pacing and streamed MP4 export."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image_folder": ("STRING", {"default": "", "tooltip": "Leave empty when photos or images is connected."}),
            "width": ("INT", {"default": 1280, "min": 64, "max": 4096, "step": 2}),
            "height": ("INT", {"default": 720, "min": 64, "max": 4096, "step": 2}),
            "fps": ("INT", {"default": 30, "min": 1, "max": 60}),
            "timing": (["BPM", "Seconds"],),
            "bpm": ("FLOAT", {"default": 128.0, "min": 20, "max": 300, "step": 1}),
            "beats_per_image": ("FLOAT", {"default": 4.0, "min": 1, "max": 16, "step": 0.5}),
            "seconds_per_image": ("FLOAT", {"default": 2.0, "min": 0.4, "max": 30, "step": 0.1}),
            "pacing": (["Dynamic", "Even"], {"tooltip": "Dynamic alternates full and half-length shots; minimum 0.4 seconds."}),
            "layout": (["Art directed mix", "Full frame", "Layered", "Split screen"],),
            "framing": (["Smart fit", "Fill", "Contain"], {"tooltip": "Smart fit preserves photos when their aspect ratio differs strongly from the scene."}),
            "transition": (["Mixed", "Whip", "Zoom", "Diagonal", "Shutter", "Impact", "Cut"],),
            "transition_seconds": ("FLOAT", {"default": 0.28, "min": 0, "max": 1, "step": 0.01}),
            "intensity": ("FLOAT", {"default": 0.75, "min": 0, "max": 1, "step": 0.05, "display": "slider"}),
            "motion_blur": (["Standard (3 samples)", "Off", "Fine (5 samples)"],),
            "grain": ("FLOAT", {"default": 0.08, "min": 0, "max": 1, "step": 0.01, "display": "slider"}),
            "accent": ("STRING", {"default": "#DFFF40"}),
            "graphics": ("BOOLEAN", {"default": True}),
            "headlines": ("STRING", {"default": "", "multiline": True, "tooltip": "One headline per image; blank lines leave that shot untitled."}),
            "font_path": ("STRING", {"default": "", "tooltip": "Optional .ttf or .otf file relative to ComfyUI/input."}),
            "audio_file": ("STRING", {"default": "", "tooltip": "Soundtrack relative to ComfyUI/input; alternatively connect AUDIO."}),
            "quality": (["High", "Preview", "Master"],),
            "shuffle": ("BOOLEAN", {"default": False}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
            "filename_prefix": ("STRING", {"default": "marioslideshow"}),
        }, "optional": {"photos": ("MARIO_IMAGES",), "images": ("IMAGE",), "audio": ("AUDIO",),
                        "beats": ("MARIO_BEATS",), "focus": ("MARIO_FOCUS",),
                        "show_counter": ("BOOLEAN", {"default": True}),
                        "show_progress": ("BOOLEAN", {"default": True}),
                        "show_headlines": ("BOOLEAN", {"default": True}),
                        "headline_layers": ("STRING", {"default": "", "multiline": True,
                            "tooltip": "Use Edit headlines. Nonempty layers replace the automatic per-image headlines. Times are seconds from video start."})},
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}}

    @classmethod
    def IS_CHANGED(cls, image_folder="", audio_file="", **kwargs):
        paths = []
        if image_folder.strip():
            paths.extend(image_files(image_folder))
        if audio_file.strip():
            paths.append(input_path(audio_file))
        return file_fingerprint(paths)

    def render(self, image_folder, width, height, fps, timing, bpm, beats_per_image,
               seconds_per_image, pacing, layout, framing, transition, transition_seconds, intensity,
               motion_blur, grain, accent, graphics, headlines, font_path, audio_file,
               quality, shuffle, seed, filename_prefix, photos=None, images=None, audio=None,
               prompt=None, extra_pnginfo=None, beats=None, focus=None, plan=None,
               show_counter=True, show_progress=True, show_headlines=True, headline_layers=""):
        sources = sum((photos is not None, images is not None, bool(image_folder.strip())))
        if sources != 1:
            raise ValueError("Supply exactly one image source: photos, images, or image_folder.")
        if audio is not None and audio_file.strip():
            raise ValueError("Use either the AUDIO socket or audio_file, not both.")
        if quality not in ("Preview", "High", "Master"):
            raise ValueError("Unknown export quality.")
        blur_samples = {"Off": 1, "Standard (3 samples)": 3, "Fine (5 samples)": 5}[motion_blur]
        settings = Settings(width=width, height=height, fps=fps, timing=timing, bpm=bpm,
                            beats_per_image=beats_per_image, seconds_per_image=seconds_per_image,
                            pacing=pacing, layout=layout, framing=framing, transition=transition,
                            transition_seconds=transition_seconds, intensity=intensity,
                            motion_blur=blur_samples, grain=grain, accent=accent,
                            graphics=graphics, font_path=str(input_path(font_path)) if font_path.strip() else "", seed=seed,
                            show_counter=show_counter, show_progress=show_progress, show_headlines=show_headlines)
        source = photos["paths"] if photos is not None else TensorPhotos(images) if images is not None else image_files(image_folder)
        labels = headlines.splitlines()
        if len(labels) > len(source):
            raise ValueError("There are more headline lines than images.")
        labels += [""] * (len(source) - len(labels))
        order = list(range(len(source)))
        if shuffle:
            np.random.default_rng(seed).shuffle(order)
        source = OrderedPhotos(source, order)
        labels = [labels[i] for i in order]
        if focus is not None:
            focus = validate_focus(focus, len(source))
            focus["items"] = [focus["items"][i] for i in order]
        if beats is not None:
            plan = build_plan(len(source), timing=timing, bpm=bpm, beats_per_image=beats_per_image,
                              seconds_per_image=seconds_per_image, pacing=pacing,
                              headlines="\n".join(labels), seed=seed, beats=beats)
            for shot in plan["shots"]:
                if layout != "Art directed mix":
                    shot["scene"] = {"Full frame": "hero", "Layered": "stack", "Split screen": "split"}[layout]
                if transition != "Mixed":
                    shot["transition"] = transition.lower()
        renderer = PromoRenderer(source, settings, labels, plan=plan, focus=focus, headline_layers=headline_layers)
        output_dir = output_path("marioslideshow")
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", filename_prefix).strip("_")[:64] or "marioslideshow"
        name = f"{prefix}_{uuid.uuid4().hex[:12]}"
        destination = output_dir / f"{name}.mp4"
        partial = output_dir / f"{name}.partial.mp4"
        poster_path = output_dir / f"{name}.jpg"
        writer = None
        Path(folder_paths.get_temp_directory()).mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="marioslideshow_", dir=folder_paths.get_temp_directory()) as temp:
                soundtrack = None
                if audio_file.strip():
                    soundtrack = input_path(audio_file)
                elif audio is not None:
                    soundtrack = Path(temp) / "audio.wav"
                    self._write_audio(audio, soundtrack, renderer.frame_count / fps)
                writer = VideoWriter(partial, settings, quality, soundtrack)
                progress = ProgressBar(renderer.frame_count)
                poster_number = min(renderer.frame_count - 1, round(fps * 0.6))
                poster = None
                for frame_number in range(renderer.frame_count):
                    throw_exception_if_processing_interrupted()
                    frame = renderer.frame(frame_number)
                    writer.write(frame)
                    if frame_number == poster_number:
                        poster = frame.copy()
                    progress.update(1)
                writer.close()
                partial.replace(destination)
            poster.save(poster_path, quality=92)
            manifest = {"settings": asdict(settings), "quality": quality, "frame_count": renderer.frame_count,
                        "duration_seconds": renderer.frame_count / fps,
                        "image_order": [order[s["image_index"]] for s in renderer.plan["shots"]] if renderer.plan else order,
                        "headlines": renderer.headlines, "shot_start_frames": renderer.starts[:-1],
                        "shot_plan": renderer.plan, "framing_data": renderer.focus, "headline_layers": renderer.headline_layers,
                        "prompt": prompt, "workflow": (extra_pnginfo or {}).get("workflow")}
            (output_dir / f"{name}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except BaseException:
            if writer is not None:
                writer.abort()
            partial.unlink(missing_ok=True)
            raise
        finally:
            renderer.clear_cache()
        video_info = {"filename": destination.name, "subfolder": "marioslideshow", "type": "output"}
        poster_info = {"filename": poster_path.name, "subfolder": "marioslideshow", "type": "output"}
        return {"ui": {"mario_video": [video_info], "mario_poster": [poster_info]},
                "result": (VideoFromFile(str(destination)), str(destination), image_tensor(poster), float(fps), renderer.frame_count)}

    @staticmethod
    def _write_audio(audio, path, duration):
        waveform = audio["waveform"]
        rate = int(audio["sample_rate"])
        if waveform.ndim != 3 or waveform.shape[0] != 1 or waveform.shape[1] not in (1, 2):
            raise ValueError("AUDIO must contain one mono or stereo waveform [1, channels, samples].")
        if not 8000 <= rate <= 192000 or waveform.shape[-1] == 0:
            raise ValueError("Audio must be nonempty with a sample rate between 8000 and 192000 Hz.")
        values = waveform[0, :, :math.ceil(duration * rate)].detach().to(device="cpu", dtype=torch.float32)
        pcm = (values.clamp(-1, 1).transpose(0, 1).numpy() * 32767).astype("<i2")
        with wave.open(str(path), "wb") as output:
            output.setnchannels(pcm.shape[1])
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(pcm.tobytes())


class MarioSlideshowFrames:
    CATEGORY = "marioslideshow"
    FUNCTION = "extract"
    RETURN_TYPES = ("IMAGE", "FLOAT")
    RETURN_NAMES = ("frames", "fps")
    DESCRIPTION = "Extract a bounded frame range for VideoHelperSuite or image processing."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "video": ("VIDEO",),
            "start_frame": ("INT", {"default": 0, "min": 0, "max": 1000000}),
            "max_frames": ("INT", {"default": 120, "min": 1, "max": 10000}),
            "memory_limit_gb": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 32, "step": 0.1}),
        }}

    def extract(self, video, start_frame, max_frames, memory_limit_gb):
        width, height = video.get_dimensions()
        count = min(max_frames, video.get_frame_count() - start_frame)
        if start_frame < 0 or count <= 0:
            raise ValueError("The requested frame range is outside the video.")
        needed = count * width * height * 3 * 4
        if needed > memory_limit_gb * 1024**3:
            raise ValueError(f"This range needs {needed / 1024**3:.2f} GB. Reduce max_frames or increase memory_limit_gb.")
        # Honor native VIDEO trim windows through the public component interface.
        if not isinstance(video, VideoFromFile) or video.get_active_trim_window() != (0.0, 0.0):
            raise ValueError("Connect the original marioslideshow VIDEO output. Use Get Video Components for other video types.")
        batch = torch.empty((count, height, width, 3), dtype=torch.float32)
        written = 0
        progress = ProgressBar(count)
        with av.open(video.get_stream_source()) as container:
            for number, frame in enumerate(container.decode(video=0)):
                throw_exception_if_processing_interrupted()
                if number < start_frame:
                    continue
                batch[written].copy_(torch.from_numpy(frame.to_ndarray(format="rgb24")))
                batch[written].div_(255)
                written += 1
                progress.update(1)
                if written == count:
                    break
        if written != count:
            raise RuntimeError("The video ended before the requested frame range.")
        return batch, float(video.get_frame_rate())


NODE_CLASS_MAPPINGS = {
    "marioslideshow": MarioSlideshow,
    "MarioSlideshowLoadImages": MarioSlideshowLoadImages,
    "MarioSlideshowFrames": MarioSlideshowFrames,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "marioslideshow": "marioslideshow",
    "MarioSlideshowLoadImages": "marioslideshow - Load Images",
    "MarioSlideshowFrames": "marioslideshow - Extract Frames",
}
