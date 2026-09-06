import importlib.util
import tempfile
import runpy
import types
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("pack_loader", Path(__file__).resolve().parents[1] / "_loader.py")
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)


def definition(name, nodes):
    return {"module": name, "legacy_names": ["msch-" + name], "nodes": nodes}


def module(nodes):
    return types.SimpleNamespace(NODE_CLASS_MAPPINGS={name: object for name in nodes},
                                 NODE_DISPLAY_NAME_MAPPINGS={name: name + " display" for name in nodes})


class LoaderTests(unittest.TestCase):
    def test_bare_entrypoint_collection_does_not_require_comfyui(self):
        result = runpy.run_path(str(Path(__file__).resolve().parents[1] / "__init__.py"))
        self.assertEqual(result["NODE_CLASS_MAPPINGS"], {})

    def test_unavailable_optional_component_does_not_hide_other_nodes(self):
        def importer(name):
            if name.endswith(".h3"):
                raise ModuleNotFoundError("optional dependency unavailable")
            return module(["Effect"])
        with self.assertLogs("msch_nodes", level="ERROR"):
            classes, names, loaded, skipped, errors = loader.load_components(
                "pack", [definition("h3", ["H3"]), definition("effect", ["Effect"])], [], importer)
        self.assertEqual(set(classes), {"Effect"})
        self.assertEqual(names["Effect"], "Effect display")
        self.assertIn("h3", errors)

    def test_legacy_component_is_never_imported_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory) / "msch-effect"
            legacy.mkdir()
            (legacy / "__init__.py").touch()
            with self.assertLogs("msch_nodes", level="WARNING"):
                classes, _, loaded, skipped, errors = loader.load_components(
                    "pack", [definition("effect", ["Effect"])], [Path(directory)],
                    lambda _: self.fail("legacy component was imported"))
            self.assertFalse(classes)
            self.assertFalse(loaded)
            self.assertIn("effect", skipped)
            self.assertFalse(errors)

    def test_disabled_legacy_folder_does_not_block_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "msch-effect.disabled"
            backup.mkdir()
            (backup / "__init__.py").touch()
            result = loader.load_components("pack", [definition("effect", ["Effect"])],
                                            [Path(directory)], lambda _: module(["Effect"]))
            self.assertEqual(set(result[0]), {"Effect"})
            self.assertFalse(result[3])

    def test_incomplete_registration_is_reported_and_next_component_loads(self):
        with self.assertLogs("msch_nodes", level="ERROR"):
            result = loader.load_components("pack", [definition("bad", ["Missing"]), definition("good", ["OK"])],
                                            [], lambda name: module([] if name.endswith(".bad") else ["OK"]))
        self.assertEqual(set(result[0]), {"OK"})
        self.assertIn("bad", result[4])

    def test_ui_only_component_is_loaded(self):
        result = loader.load_components("pack", [definition("theme", [])], [], lambda _: module([]))
        self.assertEqual(len(result[2]), 1)
        self.assertFalse(result[4])


if __name__ == "__main__":
    unittest.main()
