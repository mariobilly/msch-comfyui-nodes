import json

from ..core import schema
from ..core.audio_analysis import analyze_audio
from ..core.presets import list_preset_names
from ..core.timeline_builder import build_timeline


class SlideshowDirector:
    CATEGORY = "SlideshowForge"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "INT", "AUDIO")
    RETURN_NAMES = ("timeline_json", "image_count", "audio")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "preset": (list_preset_names(), {"default": "classic_ken_burns"}),
                "duration_mode": (
                    ["total_duration", "per_image_duration", "beat_sync"],
                    {"default": "total_duration"},
                ),
                "total_duration": ("FLOAT", {"default": 30.0, "min": 1.0, "max": 3600.0, "step": 0.5}),
                "per_image_duration": ("FLOAT", {"default": 3.0, "min": 0.3, "max": 60.0, "step": 0.1}),
                "fps": ("INT", {"default": 30, "min": 1, "max": 120}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True}),
            },
            "optional": {
                "audio": ("AUDIO",),
                "beats_per_image": ("INT", {"default": 2, "min": 1, "max": 32}),
                "timeline_json_in": ("STRING", {"multiline": True, "default": ""}),
                "on_invalid_json": (["error", "regenerate"], {"default": "error"}),
                "shuffle_order": ("BOOLEAN", {"default": False}),
                "loop": ("BOOLEAN", {"default": False}),
                "canvas_fit": (["cover", "contain_blur_bg", "contain_black_bg"], {"default": "cover"}),
                "output_width": ("INT", {"default": 0, "min": 0, "max": 8192}),
                "output_height": ("INT", {"default": 0, "min": 0, "max": 8192}),
            },
        }

    def build(
        self,
        images,
        preset,
        duration_mode,
        total_duration,
        per_image_duration,
        fps,
        seed,
        audio=None,
        beats_per_image=2,
        timeline_json_in="",
        on_invalid_json="error",
        shuffle_order=False,
        loop=False,
        canvas_fit="cover",
        output_width=0,
        output_height=0,
    ):
        image_count = int(images.shape[0])
        canvas_width = output_width if output_width > 0 else int(images.shape[2])
        canvas_height = output_height if output_height > 0 else int(images.shape[1])

        if duration_mode == "beat_sync" and audio is None:
            raise ValueError(
                "SlideshowForge: duration_mode='beat_sync' requires an 'audio' input "
                "(connect a Load Audio node's AUDIO output)."
            )

        if timeline_json_in and timeline_json_in.strip():
            try:
                candidate = json.loads(timeline_json_in)
            except json.JSONDecodeError as e:
                if on_invalid_json == "error":
                    raise ValueError(f"SlideshowForge: timeline_json_in is not valid JSON: {e}") from e
                candidate = None
            else:
                errors = schema.validate_timeline(candidate)
                if errors:
                    if on_invalid_json == "error":
                        raise ValueError(
                            "SlideshowForge: timeline_json_in failed schema validation:\n" + "\n".join(errors)
                        )
                    candidate = None

            if candidate is not None:
                for seg in candidate["segments"]:
                    if seg["image_index"] >= image_count:
                        raise ValueError(
                            f"SlideshowForge: timeline_json_in references image_index={seg['image_index']} "
                            f"but only {image_count} images were provided."
                        )
                return (json.dumps(candidate), image_count, audio)

        beats_sec = None
        bpm = None
        audio_duration_sec = None
        if duration_mode == "beat_sync":
            analysis = analyze_audio(audio["waveform"], audio["sample_rate"])
            beats_sec = analysis["beats_sec"]
            bpm = analysis["bpm"]
            audio_duration_sec = analysis["duration_sec"]
            print(
                f"[SlideshowForge] beat_sync: detected {bpm:.1f} BPM, {len(beats_sec)} beats "
                f"over {audio_duration_sec:.2f}s of audio."
            )

        timeline = build_timeline(
            image_count=image_count,
            preset_name=preset,
            duration_mode=duration_mode,
            total_duration=total_duration,
            per_image_duration=per_image_duration,
            fps=fps,
            seed=seed,
            shuffle_order=shuffle_order,
            loop=loop,
            canvas_fit=canvas_fit,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            beats_sec=beats_sec,
            beats_per_image=beats_per_image,
            bpm=bpm,
            audio_duration_sec=audio_duration_sec,
        )

        used = len(timeline["segments"])
        if duration_mode == "beat_sync" and used < image_count:
            print(
                f"[SlideshowForge] beat_sync: only {used}/{image_count} images were used -- "
                f"not enough detected beats to place a cut for every image at "
                f"beats_per_image={beats_per_image}. Lower beats_per_image, load more/denser "
                "audio, or use fewer images to use all of them."
            )

        return (json.dumps(timeline), image_count, audio)
