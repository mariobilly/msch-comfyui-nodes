"""Text overlays must render on OpenCV 4 and 5 without silently dropping effects."""
import importlib.util
import unittest
from pathlib import Path

import numpy as np
import torch

spec = importlib.util.spec_from_file_location('scanfx', Path(__file__).resolve().parents[1] / 'scanfx.py')
scanfx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanfx)


class TextEffectsTest(unittest.TestCase):
    def test_text_effects_produce_visible_finite_output(self):
        source = np.full((128, 192, 3), 0.3, dtype=np.float32)
        for name in ('hud', 'ekg', 'coderain', 'ascii'):
            with self.subTest(effect=name):
                context = dict(frame=1, total=2, t=1.0, seed=42, rng=np.random.default_rng(42))
                output = scanfx.EFFECTS[name](source.copy(), context)
                self.assertEqual(output.shape, source.shape)
                self.assertEqual(output.dtype, np.float32)
                self.assertTrue(np.isfinite(output).all())
                self.assertGreater(float(output.std()), 0.01)
                self.assertGreater(float(np.abs(output-source).mean()), 0.01)

    def test_black_mask_preserves_source_with_text_effect(self):
        source = torch.rand(2, 128, 192, 3)
        output = scanfx.ScanFX().run(source, mix=1.0, mask_feather=0, invert_mask=False,
                                    animation_speed=1.0, seed=42, mask=torch.zeros(1,128,192),
                                    effect_1='hud', strength_1=1.0)[0]
        torch.testing.assert_close(output, source)


if __name__ == '__main__':
    unittest.main()
