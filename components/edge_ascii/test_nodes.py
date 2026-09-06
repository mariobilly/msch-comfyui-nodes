import importlib.util
import sys
from pathlib import Path
import unittest

import numpy as np
import torch

from nodes import EdgeASCII, _analyze


class EdgeASCIITests(unittest.TestCase):
    def setUp(self):
        self.node = EdgeASCII()

    def test_loader_and_default_widgets(self):
        root = Path(__file__).parent
        spec = importlib.util.spec_from_file_location("edge_ascii_test_package", root / "__init__.py",
                                                    submodule_search_locations=[str(root)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.assertIsNotNone(module.NODE_CLASS_MAPPINGS["EdgeASCII"])
        kwargs = {}
        for name, definition in self.node.INPUT_TYPES()["required"].items():
            if name == "image":
                continue
            kwargs[name] = definition[0][0] if isinstance(definition[0], list) else definition[1]["default"]
        self.node.apply(torch.zeros(1, 17, 19, 3), **kwargs)

    def test_flat_images_have_no_edges_even_at_zero_threshold(self):
        for value in (0, 0.5, 1):
            source = torch.full((1, 33, 47, 3), float(value))
            output, mask = self.node.apply(source, edge_threshold=0)
            self.assertTrue(torch.equal(output, source))
            self.assertEqual(mask.count_nonzero().item(), 0)

    def test_contour_orientation(self):
        vertical = np.zeros((32, 32, 3), dtype=np.float32)
        vertical[:, 7:] = 1
        horizontal = vertical.transpose(1, 0, 2)
        for source, expected in ((vertical, 3), (horizontal, 1)):
            _, strength, _, direction = _analyze(source, 16, 0)
            self.assertTrue(np.all(direction[strength > 0.01] == expected))
        y, x = np.mgrid[:32, :32]
        for field, expected in ((x > y, 2), (x + y > 31, 4)):
            source = np.repeat(field[:, :, None], 3, axis=2).astype(np.float32)
            _, strength, _, direction = _analyze(source, 16, 0)
            self.assertTrue(np.all(direction[strength > 0.1] == expected))

    def test_all_modes_batch_odd_and_tiny_sizes(self):
        for h, w in ((1, 1), (3, 7), (31, 43)):
            source = torch.rand(2, h, w, 3)
            for mode in ("edge_only", "mixed", "full_ascii"):
                output, mask = self.node.apply(source, mode=mode)
                self.assertEqual(output.shape, source.shape)
                self.assertEqual(mask.shape, source.shape[:3])
                self.assertEqual(output.dtype, torch.float32)
                self.assertTrue(torch.isfinite(output).all())
                self.assertTrue(((output >= 0) & (output <= 1)).all())
                single, single_mask = self.node.apply(source[:1], mode=mode)
                self.assertTrue(torch.equal(output[:1], single))
                self.assertTrue(torch.equal(mask[:1], single_mask))

    def test_equal_luminance_color_boundary(self):
        source = np.zeros((32, 32, 3), dtype=np.float32)
        source[:, :7, 0] = 1
        source[:, 7:, 1] = 0.2126 / 0.7152
        _, strength, _, direction = _analyze(source, 16, 0)
        self.assertGreater(float(strength.max()), 0.1)
        self.assertTrue(np.all(direction[strength > 0.1] == 3))

    def test_zero_opacity_and_zero_selection(self):
        source = torch.rand(2, 35, 21, 3)
        for kwargs in ({"opacity": 0}, {"mask": torch.zeros(4, 5)},
                       {"mask": torch.zeros(1, 4, 5), "background": "solid"}):
            output, mask = self.node.apply(source, mode="full_ascii", **kwargs)
            self.assertTrue(torch.equal(output, source))
            self.assertEqual(mask.count_nonzero().item(), 0)

    def test_mask_broadcast_and_per_frame_selection(self):
        source = torch.full((2, 32, 32, 3), 0.5)
        full, full_mask = self.node.apply(source, mode="full_ascii")
        selected, selected_mask = self.node.apply(source, mode="full_ascii", mask=torch.ones(1, 8, 8))
        self.assertTrue(torch.equal(full, selected))
        self.assertTrue(torch.equal(full_mask, selected_mask))
        mask = torch.stack((torch.zeros(32, 32), torch.ones(32, 32)))
        output, alpha = self.node.apply(source, mode="full_ascii", mask=mask)
        self.assertTrue(torch.equal(source[0], output[0]))
        self.assertGreater(alpha[1].sum().item(), 0)

    def test_color_blending_and_strength(self):
        source = torch.zeros(1, 32, 32, 3)
        source[:, :, 7:] = 1
        output, alpha = self.node.apply(source, color="#FF0000", opacity=0.5, blur=0)
        expected = source * (1 - alpha[..., None]) + torch.tensor([1, 0, 0]) * alpha[..., None]
        torch.testing.assert_close(output, expected)
        _, fewer = self.node.apply(source, edge_threshold=0.9)
        self.assertGreater(alpha.sum().item(), fewer.sum().item())

    def test_invalid_colors_and_mask_batch(self):
        self.assertIs(self.node.VALIDATE_INPUTS("#FFFF00", "000000"), True)
        self.assertIsInstance(self.node.VALIDATE_INPUTS("yellow", "000000"), str)
        with self.assertRaises(ValueError):
            self.node.apply(torch.zeros(2, 16, 16, 3), mask=torch.ones(3, 16, 16))


if __name__ == "__main__":
    unittest.main()
