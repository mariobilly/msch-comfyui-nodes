"""Validate the single package, component catalog and browser import paths."""
import ast
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import urljoin

root = Path(__file__).resolve().parents[1]
metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
assert metadata["project"]["name"] == "msch-comfyui-nodes"
assert metadata["tool"]["comfy"]["PublisherId"] == "mariobilly"
assert re.fullmatch(r"\d+\.\d+\.\d+", metadata["project"]["version"])
definitions = json.loads((root / "components.json").read_text())
expected = json.loads((root / "node_list.json").read_text(encoding="utf-8"))
nodes = []
for component in definitions:
    directory = root / "components" / component["module"]
    assert (directory / "__init__.py").is_file()
    nodes.extend(component["nodes"])
    assert set(component["nodes"]) == set(json.loads((directory / "node_list.json").read_text(encoding="utf-8")))
    if component.get("web_entry"):
        assert (directory / "web" / component["web_entry"]).is_file()
    for script in (directory / "web").rglob("*.js"):
        served = "https://comfy.test/msch_nodes/assets/" + component["module"] + "/" + script.relative_to(directory / "web").as_posix()
        for target in re.findall(r'''(?:from\s+|import\s*)["']([^"']+)["']''', script.read_text(encoding="utf-8")):
            if "/scripts/" in target:
                assert urljoin(served, target).startswith("https://comfy.test/scripts/"), (script, target)
assert len(nodes) == len(set(nodes))
assert set(nodes) == set(expected)
for path in root.rglob("*.py"):
    if ".git" not in path.parts:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
for path in root.rglob("*.json"):
    if ".git" in path.parts:
        continue
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(value, dict) and isinstance(value.get("nodes"), list):
        ids = {node["id"] for node in value["nodes"]}
        assert len(ids) == len(value["nodes"]), path
        for link in value.get("links", []):
            if isinstance(link, list):
                assert link[1] in ids and link[3] in ids, path
assert len(list((root / "web").rglob("*.js"))) == 1, "Only the bootstrap should be auto-loaded"
print(f"Validated one package, {len(definitions)} components, {len(nodes)} unique node IDs and browser import paths.")
