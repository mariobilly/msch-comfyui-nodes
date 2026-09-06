import json
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import PromoRenderer, Settings
from titles import parse_titles


class HeadlineTests(unittest.TestCase):
    def renderer(self, layers=None, **settings):
        defaults = dict(width=320, height=180, fps=20, timing="Seconds", seconds_per_image=2,
                        layout="Full frame", motion_blur=1, grain=0, graphics=False)
        defaults.update(settings)
        return PromoRenderer([Image.new("RGB", (320, 180), (40, 40, 40))], Settings(**defaults),
                             headlines=["AUTOMATIC"], headline_layers=layers)

    def test_counter_and_progress_are_independent(self):
        off = self.renderer(graphics=True, show_counter=False, show_progress=False, show_headlines=False)
        counter = self.renderer(graphics=True, show_counter=True, show_progress=False, show_headlines=False)
        progress = self.renderer(graphics=True, show_counter=False, show_progress=True, show_headlines=False)
        base, c, p = [np.asarray(r.frame(10)) for r in (off, counter, progress)]
        self.assertTrue(np.any(base[:45] != c[:45]))
        np.testing.assert_array_equal(base[45:], c[45:])
        self.assertTrue(np.any(base[-2:] != p[-2:]))
        np.testing.assert_array_equal(base[:-2], p[:-2])

    def test_multiple_layers_have_independent_positions_and_times(self):
        layers = [{"text":"FIRST", "x":5, "y":5, "width":40, "start":0.2, "end":0.8, "animation":"none"},
                  {"text":"SECOND", "x":55, "y":60, "width":40, "start":0.5, "end":1.5, "animation":"none"}]
        r = self.renderer(json.dumps(layers))
        plain = self.renderer(show_headlines=False)
        for number, top, bottom in ((0, False, False), (6, True, False), (12, True, True), (20, False, True), (32, False, False)):
            diff = np.any(np.asarray(r.frame(number)) != np.asarray(plain.frame(number)), axis=2)
            self.assertEqual(bool(diff[:70,:160].any()), top)
            self.assertEqual(bool(diff[90:,160:].any()), bottom)
        hidden = self.renderer(layers, show_headlines=False)
        np.testing.assert_array_equal(hidden.frame(12), plain.frame(12))

    def test_long_text_at_edge_is_fitted_and_disabled_layers_stay_hidden(self):
        r = self.renderer([{"text":"LONGWORD"*100, "x":98, "y":98, "size":50, "animation":"slide"}])
        bitmap, x, y = r._title_cached(0)
        self.assertLessEqual(x + bitmap.width, 320)
        self.assertLessEqual(y + bitmap.height, 180)
        self.assertEqual(r.frame(10).size, (320,180))
        r = self.renderer([{"text":"HIDDEN", "enabled":False}])
        np.testing.assert_array_equal(r.frame(10), self.renderer(show_headlines=False).frame(10))

    def test_bad_titles_are_rejected(self):
        for layer in ({"end":0}, {"start":float("nan")}, {"x":-1}, {"width":0}, {"size":100},
                      {"align":"unknown"}, {"enabled":"false"}, {"unknown":1}):
            with self.subTest(layer=layer), self.assertRaises(ValueError):
                parse_titles([layer])
        self.assertEqual(parse_titles("  "), [])
        with self.assertRaises(ValueError):
            parse_titles([{}]*201)


if __name__ == "__main__":
    unittest.main()
