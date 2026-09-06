import math
import sys
import tempfile
import unittest
import wave
from dataclasses import replace
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import PromoRenderer, Settings, VideoWriter, open_photo


def photos():
    result = []
    for index, size in enumerate([(300, 200), (200, 300), (240, 240), (400, 180), (180, 400), (300, 200), (240, 240), (300, 200)]):
        image = Image.new("RGB", size, (45 + index * 20, 70, 170 - index * 12))
        draw = ImageDraw.Draw(image)
        for x in range(0, size[0], 25):
            draw.line((x, 0, x + 50, size[1]), fill=(220, 200, 90), width=5)
        result.append(image)
    return result


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(width=192, height=108, fps=24, grain=0, motion_blur=1)

    def test_timing_rounds_cumulative_beats(self):
        s = replace(self.settings, bpm=127, pacing="Even")
        r = PromoRenderer(photos(), s)
        self.assertEqual(r.frame_count, round(8 * 60 / 127 * 4 * 24))
        for i, start in enumerate(r.starts):
            self.assertEqual(start, round(i * 60 / 127 * 4 * 24))
        dynamic = PromoRenderer(photos(), replace(s, pacing="Dynamic"))
        self.assertEqual(dynamic.frame_count, round(6 * 60 / 127 * 4 * 24))

    def test_all_scenes_and_aspects_have_content(self):
        for width, height in ((192, 108), (108, 192), (128, 128)):
            for layout in ("Art directed mix", "Full frame", "Layered", "Split screen"):
                r = PromoRenderer(photos(), replace(self.settings, width=width, height=height, layout=layout))
                for i in range(8):
                    frame = r.frame((r.starts[i] + r.starts[i + 1]) // 2)
                    self.assertEqual(frame.size, (width, height))
                    self.assertGreater(np.asarray(frame).std(), 10)
                    self.assertGreater(np.asarray(frame).mean(), 20)

    def test_transition_endpoints_and_no_unfilled_pixels(self):
        a, b = Image.new("RGB", (192, 108), "#994444"), Image.new("RGB", (192, 108), "#449999")
        for transition in ("Whip", "Zoom", "Diagonal", "Shutter", "Impact"):
            r = PromoRenderer(photos(), replace(self.settings, transition=transition))
            np.testing.assert_array_equal(r._transition(a, b, 0, 1), a)
            np.testing.assert_array_equal(r._transition(a, b, 1, 1), b)
            for q in (0.01, 0.25, 0.5, 0.75, 0.99):
                frame = np.asarray(r._transition(a, b, q, 1))
                self.assertTrue((frame.sum(axis=2) > 0).all(), transition)

    def test_motion_and_seeded_grain_are_reproducible(self):
        r = PromoRenderer(photos(), replace(self.settings, grain=0.1, motion_blur=3), ["A headline"])
        np.testing.assert_array_equal(r.frame(10), r.frame(10))
        self.assertGreater(np.abs(np.asarray(r.frame(2), dtype=float) - np.asarray(r.frame(20), dtype=float)).mean(), 1)

    def test_single_image_and_extreme_caption(self):
        for size in ((64, 64), (108, 192)):
            r = PromoRenderer(photos()[:1], replace(self.settings, width=size[0], height=size[1]), ["W" * 240])
            self.assertEqual(r.frame(r.frame_count - 1).size, size)
            with self.assertRaises(IndexError):
                r.frame(r.frame_count)

    def test_bad_dimensions_and_empty_sources(self):
        with self.assertRaises(ValueError):
            Settings(width=191)
        with self.assertRaises(ValueError):
            PromoRenderer([], self.settings)

    def test_transparent_png_has_deliberate_matte(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "alpha.png"
            Image.new("RGBA", (100, 100), (255, 0, 0, 0)).save(path)
            self.assertEqual(open_photo(path).getpixel((0, 0)), (18, 18, 20))


class ExportTests(unittest.TestCase):
    def test_mp4_has_exact_frames_and_pads_short_audio(self):
        s = Settings(width=192, height=108, fps=24, timing="Seconds", seconds_per_image=0.5,
                     pacing="Even", grain=0, motion_blur=1)
        r = PromoRenderer(photos()[:2], s)
        with tempfile.TemporaryDirectory() as temp:
            audio_path = Path(temp) / "audio.wav"
            with wave.open(str(audio_path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                signal = np.sin(np.arange(1600) * 2 * math.pi * 440 / 16000) * 8000
                audio.writeframes(signal.astype("<i2").tobytes())
            path = Path(temp) / "test.mp4"
            writer = VideoWriter(path, s, "Preview", audio_path)
            for number in range(r.frame_count):
                writer.write(r.frame(number))
            writer.close()
            with av.open(str(path)) as container:
                self.assertEqual(len(container.streams.audio), 1)
                self.assertAlmostEqual(float(container.streams.video[0].average_rate), 24)
                self.assertEqual(sum(1 for _ in container.decode(video=0)), r.frame_count)
            with av.open(str(path)) as container:
                audio_frames = list(container.decode(audio=0))
                self.assertGreater(sum(f.samples for f in audio_frames), 15000)

    def test_abort_removes_partial_video(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cancelled.mp4"
            s = Settings(width=192, height=108)
            writer = VideoWriter(path, s, "Preview")
            writer.write(Image.new("RGB", (192, 108)))
            writer.abort()
            self.assertFalse(path.exists())
            self.assertIsNotNone(writer.process.poll())


if __name__ == "__main__":
    unittest.main()
