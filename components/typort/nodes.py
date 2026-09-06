import json
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
from PIL import Image

import folder_paths
from comfy.model_management import throw_exception_if_processing_interrupted
from comfy.utils import ProgressBar

from .project import FONTS, FORMATS, PRESETS, default_project, validate_project
from .render import render


class MarioTyport:
    CATEGORY = "mariotyport"
    FUNCTION = "export"
    RETURN_TYPES = ("STRING", "IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("export_path", "poster", "alpha_mask", "project_json")
    OUTPUT_NODE = True
    DESCRIPTION = "Standalone animated typography. Open the studio for layers, timing and styling. Transparent exports do not include footage."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "text": ("STRING", {"default": "MAKE\nIT MATTER", "multiline": True}),
            "font": (FONTS,), "animation": (PRESETS,),
            "duration": ("FLOAT", {"default": 5, "min": 0.1, "max": 600, "step": 0.1}),
            "width": ("INT", {"default": 1920, "min": 64, "max": 4096, "step": 2}),
            "height": ("INT", {"default": 1080, "min": 64, "max": 4096, "step": 2}),
            "fps": ("INT", {"default": 30, "min": 1, "max": 60}),
            "format": (FORMATS,),
            "motion_blur": (["Off", "3 samples", "5 samples"], {"default": "3 samples"}),
            "video_file": ("STRING", {"default": ""}),
            "project_json": ("STRING", {"default": "", "multiline": True}),
            "filename_prefix": ("STRING", {"default": "mariotyport"}),
        }}

    def export(self, text, font, animation, duration, width, height, fps, format,
               motion_blur, video_file, project_json, filename_prefix):
        project = validate_project(project_json) if project_json.strip() else validate_project(default_project(text, font, animation, duration))
        video = None
        audio = None
        if project["audio"]["file"]:
            base = Path(folder_paths.get_input_directory()).resolve()
            audio = (base / project["audio"]["file"]).resolve()
            if not audio.is_relative_to(base) or not audio.is_file():
                raise ValueError("Upload the project's soundtrack into ComfyUI/input again.")
        if video_file.strip():
            video = Path(video_file.strip().strip('"')).expanduser()
            if not video.is_absolute():
                video = Path(folder_paths.get_input_directory()) / video
            if not video.is_file():
                raise ValueError(f"Video file not found: {video}")
        prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", filename_prefix)[:60] or "mariotyport"
        name = prefix + "_" + uuid.uuid4().hex[:12]
        output = Path(folder_paths.get_output_directory()) / "mariotyport" / name
        output.parent.mkdir(parents=True, exist_ok=True)
        cancel = threading.Event()
        progress = ProgressBar(max(1, round(project["duration"] * fps)))
        # ComfyUI may call synchronous nodes from its asyncio loop; Playwright owns a separate thread.
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(render, project, output, width, height, fps, format,
                                     {"Off": 1, "3 samples": 3, "5 samples": 5}[motion_blur], video,
                                     cancel, lambda done, total: progress.update_absolute(done, total), audio)
            try:
                while not future.done():
                    throw_exception_if_processing_interrupted()
                    time.sleep(0.1)
                result = future.result()
            except BaseException:
                cancel.set()
                raise
        with Image.open(result["poster"]) as image:
            poster = torch.from_numpy(np.asarray(image.convert("RGB"), dtype=np.float32).copy() / 255).unsqueeze(0)
        with Image.open(result["alpha"]) as image:
            alpha = torch.from_numpy(np.asarray(image.getchannel("A"), dtype=np.float32).copy() / 255).unsqueeze(0)
        def info(path):
            return {"filename": Path(path).name, "subfolder": f"mariotyport/{name}", "type": "output"}
        return {"ui": {"mariotyport_video": [info(result["preview"])], "images": [info(result["poster"])],
                       "mariotyport_export": [info(result["path"])] if format != "PNG sequence" else [],
                       "mariotyport_path": [result["path"]]},
                "result": (result["path"], poster, alpha, json.dumps(project, ensure_ascii=False))}
