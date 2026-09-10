"""Exercise real node entry points and checkpoint loading with optional runtime deps."""
import importlib
import importlib.util
import os
import pickle
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
DEPS = ("numpy", "torch", "cv2", "av", "librosa", "playwright", "demucs", "aiohttp")
HAS_DEPS = all(importlib.util.find_spec(name) is not None for name in DEPS)


def package(name, path):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    return module


def defaults(cls):
    result = {}
    for key, value in cls.INPUT_TYPES()["required"].items():
        options = value[1] if len(value) > 1 else {}
        result[key] = options.get("default", value[0][0] if isinstance(value[0], list) else None)
    return result


@unittest.skipUnless(HAS_DEPS, "Requires the optional ComfyUI media/runtime dependencies")
class NodeSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "input"
        self.output = self.root / "output"
        self.input.mkdir()
        self.output.mkdir()
        folders = types.ModuleType("folder_paths")
        folders.get_input_directory = lambda: str(self.input)
        folders.get_output_directory = lambda: str(self.output)
        folders.get_temp_directory = lambda: str(self.root / "temp")
        folders.models_dir = str(self.root / "models")
        from aiohttp import web
        modules = {
            "folder_paths": folders,
            "comfy": package("comfy", self.root),
            "comfy.model_management": types.SimpleNamespace(throw_exception_if_processing_interrupted=lambda: None),
            "comfy.utils": types.SimpleNamespace(ProgressBar=Mock()),
            "comfy_api": package("comfy_api", self.root),
            "comfy_api.input_impl": types.SimpleNamespace(VideoFromFile=Mock()),
            "server": types.SimpleNamespace(PromptServer=types.SimpleNamespace(
                instance=types.SimpleNamespace(routes=web.RouteTableDef()))),
        }
        # Use actual component modules, without starting ComfyUI or its root loader.
        for subdir in ("", "components", "components/puppet_face", "components/typort",
                       "components/slideshow", "components/a2v", "components/a2v/mscha2v",
                       "components/a2v/mscha2v/nodes"):
            name = "_security_pack" + ("." + subdir.replace("/", ".") if subdir else "")
            modules[name] = package(name, ROOT / subdir)
        original = {name: sys.modules.get(name) for name in modules}
        sys.modules.update(modules)

        def restore():
            # Do not unload newly imported native libraries (torch, NumPy, cv2).
            for name in list(sys.modules):
                if name.startswith("_security_pack"):
                    sys.modules.pop(name, None)
            for name, previous in original.items():
                if previous is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous

        self.addCleanup(restore)

    def module(self, name):
        return importlib.import_module("_security_pack.components." + name)

    def test_all_reported_read_resolvers_reject_host_paths(self):
        puppet = self.module("puppet_face.nodes")
        slides = self.module("slideshow.nodes")
        advanced = self.module("slideshow.advanced_nodes")
        audio = self.module("a2v.mscha2v.nodes._common")
        route = self.module("typort.audio_routes")
        outside = self.root / "secret.wav"
        outside.write_bytes(b"secret")
        for value in (str(outside), "../secret.wav", "sub/../../secret.wav", "C:\\secret.wav"):
            readers = [lambda: puppet.PuppetFaceLoadVideo().load(value, 1, 1, 0),
                       lambda: puppet.PuppetFaceLoadVideo.IS_CHANGED(value, 1, 1, 0),
                       lambda: slides.image_files(value),
                       lambda: slides.MarioSlideshow.IS_CHANGED(audio_file=value),
                       lambda: advanced.resolve_file(value),
                       lambda: audio.resolve_audio_path(value),
                       lambda: route.input_audio(value)]
            for index, read in enumerate(readers):
                with self.subTest(value=value, reader=index), self.assertRaises(ValueError):
                    read()

    def test_typort_video_rejected_before_render(self):
        typort = self.module("typort.nodes")
        args = defaults(typort.MarioTyport)
        args["video_file"] = "../secret.mp4"
        with patch.object(typort, "render") as render, self.assertRaises(ValueError):
            typort.MarioTyport().export(**args)
        render.assert_not_called()

    def test_slideshow_soundtrack_and_font_rejected_before_writer(self):
        import torch
        slides = self.module("slideshow.nodes")
        for field in ("audio_file", "font_path"):
            args = defaults(slides.MarioSlideshow)
            args.update(images=torch.zeros((1, 16, 16, 3)))
            args[field] = "../secret.wav"
            with self.subTest(field=field), patch.object(slides, "PromoRenderer"), \
                    patch.object(slides, "VideoWriter") as writer, self.assertRaises(ValueError):
                slides.MarioSlideshow().render(**args)
            writer.assert_not_called()

    def test_puppet_output_rejected_before_writer(self):
        puppet = self.module("puppet_face.nodes")
        for prefix in (str(self.root / "escape"), "../escape", "nested/../../escape", "C:\\escape"):
            with self.subTest(prefix=prefix), patch("cv2.VideoWriter") as writer, self.assertRaises(ValueError):
                puppet.PuppetFaceSaveVideo().save(None, 24, prefix)
            writer.assert_not_called()

    def test_valid_video_read_write_and_input_resolvers(self):
        import cv2
        import numpy as np
        from PIL import Image
        puppet = self.module("puppet_face.nodes")
        src = self.input / "clip.mp4"
        writer = cv2.VideoWriter(str(src), cv2.VideoWriter_fourcc(*"mp4v"), 24, (32, 32))
        self.assertTrue(writer.isOpened())
        for _ in range(3):
            writer.write(np.zeros((32, 32, 3), dtype=np.uint8))
        writer.release()
        frames, fps, count = puppet.PuppetFaceLoadVideo().load("clip.mp4", 0, 1, 0)
        self.assertEqual(count, 3)
        result = puppet.PuppetFaceSaveVideo().save(frames, fps, "nested/safe")
        dest = Path(result["result"][0])
        self.assertTrue(dest.is_relative_to(self.output))
        self.assertTrue(dest.is_file())
        Image.new("RGB", (16, 16)).save(self.input / "photo.png")
        slides = self.module("slideshow.nodes")
        self.assertEqual(slides.image_files("."), [self.input / "photo.png"])
        self.assertEqual(self.module("slideshow.advanced_nodes").resolve_file("clip.mp4"), src)
        self.assertEqual(self.module("a2v.mscha2v.nodes._common").resolve_audio_path("clip.mp4"), str(src))

    def test_directory_entry_symlink_cannot_escape(self):
        outside = self.root / "secret.png"
        outside.write_bytes(b"secret")
        try:
            (self.input / "photo.png").symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Host cannot create symlinks: {exc}")
        with self.assertRaises(ValueError):
            self.module("slideshow.nodes").image_files(".")

    def test_checkpoint_checksum_rejected_before_deserialization(self):
        analysis = self.module("typort.audio_analysis")
        checkpoint = self.root / "bad.th"
        checkpoint.write_bytes(b"untrusted")
        with patch("torch.load") as load, self.assertRaisesRegex(ValueError, "checksum"):
            analysis.load_demucs_checkpoint(checkpoint)
        load.assert_not_called()

    def test_restricted_unpickler_rejects_code_even_past_checksum_layer(self):
        import torch
        analysis = self.module("typort.audio_analysis")
        marker = self.root / "executed"

        class Payload:
            def __reduce__(self):
                return eval, (f"__import__('pathlib').Path({str(marker)!r}).touch()",)

        checkpoint = self.root / "payload.th"
        torch.save(Payload(), checkpoint)
        digest = "8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4"
        with patch.object(analysis.hashlib, "sha256", return_value=Mock(hexdigest=lambda: digest)), \
                self.assertRaises(pickle.UnpicklingError):
            analysis.load_demucs_checkpoint(checkpoint)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(os.environ.get("MSCH_DEMUCS_CHECKPOINT"), "Set MSCH_DEMUCS_CHECKPOINT to test the official model")
    def test_official_model_loads_with_restricted_unpickler(self):
        from demucs.states import load_model
        analysis = self.module("typort.audio_analysis")
        model = load_model(analysis.load_demucs_checkpoint(os.environ["MSCH_DEMUCS_CHECKPOINT"]), strict=True)
        self.assertEqual(model.sources, ["drums", "bass", "other", "vocals"])
        self.assertEqual(model.samplerate, 44100)


if __name__ == "__main__":
    unittest.main()
