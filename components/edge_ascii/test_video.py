import importlib.util
from fractions import Fraction
from pathlib import Path
import sys
import tempfile
import unittest

import av
import torch
from comfy_api.latest import InputImpl, Types


ROOT = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("msch_video_test", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
PACKAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PACKAGE
SPEC.loader.exec_module(PACKAGE)
VideoNode = PACKAGE.NODE_CLASS_MAPPINGS["MschEdgeASCIIVideo"]


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.image = torch.full((1, 23, 31, 3), 0.5)
        self.settings = {"mode": "full_ascii", "fill_amount": 1.0}

    def test_still_becomes_moving_video_with_correct_duration(self):
        for animation in ("flow", "pulse"):
            result = VideoNode().animate(image=self.image, fps=12, duration_seconds=1,
                                         animation=animation, **self.settings)[0]
            parts = result.get_components()
            self.assertEqual(parts.images.shape, (12, 24, 32, 3))
            self.assertEqual(parts.frame_rate, Fraction(12))
            self.assertFalse(torch.equal(parts.images[0], parts.images[3]))
            self.assertTrue(torch.isfinite(parts.images).all())

    def test_native_video_keeps_frame_rate_count_and_audio(self):
        source = self.image.expand(7, -1, -1, -1).clone()
        source[-1] = 0.1
        audio = {"waveform": torch.zeros(1, 2, 24000), "sample_rate": 48000}
        clip = InputImpl.VideoFromComponents(Types.VideoComponents(images=source, frame_rate=Fraction(30000, 1001), audio=audio))
        parts = VideoNode().animate(video=clip, animation="none", **self.settings)[0].get_components()
        self.assertEqual(len(parts.images), 7)
        self.assertEqual(parts.frame_rate, Fraction(30000, 1001))
        self.assertIs(parts.audio, audio)
        self.assertFalse(torch.equal(parts.images[0], parts.images[-1]))

    def test_no_animation_and_zero_mask(self):
        parts = VideoNode().animate(image=self.image, fps=8, duration_seconds=1, animation="none", **self.settings)[0].get_components()
        self.assertTrue(torch.equal(parts.images[0], parts.images[-1]))
        parts = VideoNode().animate(image=self.image, fps=8, duration_seconds=1, mask=torch.zeros(23, 31), **self.settings)[0].get_components()
        torch.testing.assert_close(parts.images, torch.full_like(parts.images, 0.5))

    def test_batch_masks_and_reject_ambiguous_input(self):
        batch = self.image.expand(2, -1, -1, -1).clone()
        mask = torch.stack((torch.zeros(23, 31), torch.ones(23, 31)))
        parts = VideoNode().animate(image=batch, mask=mask, animation="none", **self.settings)[0].get_components()
        self.assertTrue(torch.equal(parts.images[0, :23, :31], batch[0]))
        self.assertFalse(torch.equal(parts.images[1, :23, :31], batch[1]))
        with self.assertRaises(ValueError):
            VideoNode().animate()
        with self.assertRaises(ValueError):
            VideoNode().animate(image=batch, video=object())

    def test_mp4_round_trip_with_audio(self):
        soundtrack = {"waveform": torch.zeros(1, 2, 48000), "sample_rate": 48000}
        clip = VideoNode().animate(image=self.image, fps=12, duration_seconds=1, audio=soundtrack, **self.settings)[0]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.mp4"
            clip.save_to(str(path), format=Types.VideoContainer.MP4, codec=Types.VideoCodec.H264)
            with av.open(str(path)) as container:
                self.assertEqual(container.streams.video[0].codec_context.name, "h264")
                self.assertEqual(len(container.streams.audio), 1)
                self.assertAlmostEqual(float(container.streams.video[0].duration * container.streams.video[0].time_base), 1.0, places=2)
                frames = [frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)]
            self.assertEqual(len(frames), 12)
            self.assertEqual(frames[0].shape, (24, 32, 3))
            self.assertFalse((frames[0] == frames[3]).all())


if __name__ == "__main__":
    unittest.main()
