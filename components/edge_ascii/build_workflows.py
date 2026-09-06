"""Generate native ComfyUI workflows with MP4 output."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parent


def main():
    spec = importlib.util.spec_from_file_location("msch_workflow", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    schema = package.NODE_CLASS_MAPPINGS["MschEdgeASCIIVideo"].INPUT_TYPES()
    values = [d[0][0] if isinstance(d[0], list) else d[1]["default"] for d in schema["required"].values()]
    common = {"flags": {}, "mode": 0}
    effect = {
        **common, "id": 2, "type": "MschEdgeASCIIVideo", "pos": [430, 60], "size": [380, 730], "order": 1,
        "inputs": [{"name": k, "type": d[0], "link": None} for k, d in schema["optional"].items()],
        "outputs": [{"name": "video", "type": "VIDEO", "links": [2], "slot_index": 0}],
        "properties": {"Node name for S&R": "MschEdgeASCIIVideo"}, "widgets_values": values,
    }
    save = {
        **common, "id": 3, "type": "SaveVideo", "pos": [890, 100], "size": [390, 440], "order": 2,
        "inputs": [{"name": "video", "type": "VIDEO", "link": 2}],
        "outputs": [{"name": "video", "type": "VIDEO", "links": None}],
        "properties": {"Node name for S&R": "SaveVideo"}, "widgets_values": ["video/msch-edge-ascii", "mp4"],
    }
    for use_video, name in ((False, "edge_ascii"), (True, "edge_ascii_video_input")):
        kind = "VIDEO" if use_video else "IMAGE"
        loader = "LoadVideo" if use_video else "LoadImage"
        load = {
            **common, "id": 1, "type": loader, "pos": [50, 100], "size": [310, 340], "order": 0, "inputs": [],
            "outputs": [{"name": kind, "type": kind, "links": [1], "slot_index": 0}],
            "properties": {"Node name for S&R": loader},
            "widgets_values": ["select_your_video.mp4"] if use_video else ["select_your_image.png", "image"],
        }
        if not use_video:
            load["outputs"].append({"name": "MASK", "type": "MASK", "links": None})
        current = copy.deepcopy(effect)
        slot = 1 if use_video else 0
        current["inputs"][slot]["link"] = 1
        if use_video:
            current["widgets_values"][2] = "none"
        workflow = {"last_node_id": 3, "last_link_id": 2, "nodes": [load, current, save],
                    "links": [[1, 1, 0, 2, slot, kind], [2, 2, 0, 3, 0, "VIDEO"]],
                    "groups": [], "config": {}, "extra": {"ds": {"scale": 0.85, "offset": [30, 30]}}, "version": 0.4}
        (ROOT / "workflows" / (name + ".json")).write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
        settings = dict(zip(schema["required"], current["widgets_values"]))
        settings["video" if use_video else "image"] = ["1", 0]
        prompt = {
            "1": {"class_type": loader, "inputs": {"file" if use_video else "image": load["widgets_values"][0]}},
            "2": {"class_type": "MschEdgeASCIIVideo", "inputs": settings},
            "3": {"class_type": "SaveVideo", "inputs": {"video": ["2", 0], "filename_prefix": "video/msch-edge-ascii", "format": {"format": "mp4", "codec": {"codec": "h264", "encoding": {"encoding": "auto"}}}}},
        }
        (ROOT / "workflows" / (name + "_api.json")).write_text(json.dumps(prompt, indent=2) + "\n", encoding="utf-8")
    print("Built photo and video workflows with MP4 outputs.")


if __name__ == "__main__":
    main()
