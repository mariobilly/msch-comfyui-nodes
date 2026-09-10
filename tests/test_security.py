"""Dependency-free regressions for workflow path and executable boundaries."""
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


paths = load_file("security_paths", "components/_paths.py")


class PathSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "input"
        self.base.mkdir()
        (self.base / "media").mkdir()
        (self.base / "media" / "song.wav").write_bytes(b"audio")
        self.outside = self.root / "input-other"
        self.outside.mkdir()
        (self.outside / "secret.wav").write_bytes(b"secret")

    def test_existing_input_and_nested_output(self):
        for name in ("media/song.wav", "media\\song.wav"):
            self.assertEqual(paths.resolve_path(self.base, name, kind="file"),
                             self.base / "media" / "song.wav")
        self.assertEqual(paths.resolve_path(self.base, "new/video.mp4"), self.base / "new/video.mp4")
        self.assertEqual(paths.resolve_path(self.base, ".", kind="directory"), self.base)

    def test_absolute_traversal_drive_unc_and_stream_paths_rejected(self):
        for name in (str(self.base / "media/song.wav"), str(self.outside / "secret.wav"),
                     "/etc/passwd", "../input-other/secret.wav", "media/../media/song.wav",
                     "media\\..\\song.wav", "C:\\secret.wav", "C:secret.wav", "\\secret.wav",
                     "\\\\server\\share\\file", "//server/share/file", "file:stream", "bad\x00file", "", None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                paths.resolve_path(self.base, name)

    def test_missing_file_and_wrong_kind_rejected(self):
        for name, kind in (("missing.wav", "file"), ("media", "file"), ("media/song.wav", "directory")):
            with self.subTest(name=name), self.assertRaises(FileNotFoundError):
                paths.resolve_path(self.base, name, kind=kind)

    def test_symlink_escape_for_reads_and_new_writes(self):
        try:
            (self.base / "linked").symlink_to(self.outside, target_is_directory=True)
            (self.base / "song.wav").symlink_to(self.outside / "secret.wav")
        except OSError as exc:
            self.skipTest(f"Host cannot create symlinks: {exc}")
        for name in ("linked/secret.wav", "linked/new.mp4", "song.wav"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                paths.resolve_path(self.base, name)

    def test_wrappers_use_host_directories(self):
        folders = types.SimpleNamespace(get_input_directory=lambda: str(self.base),
                                        get_output_directory=lambda: str(self.outside))
        with patch.dict(sys.modules, folder_paths=folders):
            self.assertEqual(paths.input_path("media/song.wav"), self.base / "media/song.wav")
            self.assertEqual(paths.output_path("new.mp4"), self.outside / "new.mp4")


class WhisperSecurityTests(unittest.TestCase):
    def setUp(self):
        # NumPy is used only for audio conversion, outside these launch tests.
        with patch.dict(sys.modules, numpy=types.ModuleType("numpy")):
            self.aligner = load_file("security_aligner", "components/lyric_sync/aligner.py")

    def test_workflow_override_cannot_select_executable(self):
        with patch.object(self.aligner.shutil, "which", return_value="/trusted/whisperx") as which:
            self.assertEqual(self.aligner.resolve_whisperx("/attacker/payload"), "/trusted/whisperx")
            which.assert_called_once_with("whisperx")

    def test_known_fallback_ignores_existing_override(self):
        with patch.object(self.aligner.shutil, "which", return_value=None), \
                patch.object(self.aligner.os.path, "isfile", return_value=True) as isfile:
            self.assertEqual(self.aligner.resolve_whisperx("/attacker/payload"), self.aligner._KNOWN_WHISPERX)
            isfile.assert_called_once_with(self.aligner._KNOWN_WHISPERX)

    def test_direct_runner_also_ignores_override(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(self.aligner, "resolve_whisperx", return_value="/trusted/whisperx"), \
                patch.object(self.aligner.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as run:
            self.aligner.run_whisperx("song.wav", directory, exe="/attacker/payload")
            self.assertEqual(run.call_args.args[0][0], "/trusted/whisperx")
            self.assertNotIn("/attacker/payload", run.call_args.args[0])
            self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_missing_installation_never_launches_override(self):
        with patch.object(self.aligner, "resolve_whisperx", return_value=None), \
                patch.object(self.aligner.subprocess, "run") as run:
            self.assertIsNone(self.aligner.run_whisperx("song.wav", ".", exe="/attacker/payload"))
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
