import unittest
import support
from mariotyport.project import default_project, validate_project


class ProjectTests(unittest.TestCase):
    def test_defaults(self):
        project = default_project()
        self.assertEqual(validate_project(project), project)

    def test_reject_bad_layers(self):
        for field, value in (("font", "../bad"), ("x", float("nan")), ("end", -1),
                             ("color", "red"), ("text", "x" * 2001), ("enabled", 1)):
            with self.subTest(field=field):
                project = default_project()
                project["layers"][0][field] = value
                with self.assertRaises(ValueError):
                    validate_project(project)

    def test_keyframes(self):
        p = default_project()
        p["layers"][0]["keyframes"] = [{"time": 1, "x": 0.3, "y": 0.6, "scale": 1, "rotation": 0, "opacity": 1}]
        self.assertEqual(validate_project(p), p)
        p["layers"][0]["keyframes"] *= 2
        with self.assertRaises(ValueError):
            validate_project(p)

    def test_deep_copy(self):
        p = default_project()
        normalized = validate_project(p)
        normalized["layers"][0]["curve"][0] = 0.5
        self.assertNotEqual(p, normalized)

    def test_bad_json_and_counts(self):
        for p in ("not-json", {}, {"version": 2}, {**default_project(), "layers": []}):
            with self.assertRaises(ValueError):
                validate_project(p)


if __name__ == "__main__":
    unittest.main()
