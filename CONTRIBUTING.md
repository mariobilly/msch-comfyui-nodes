# Adding nodes and releasing updates

This repository is the canonical home of MSCH Nodes. Add future nodes here; do not create a separate Registry package for each component.

## Component structure

Each component lives in `components/<name>/` with its own `__init__.py`, implementation, `node_list.json`, `docs/NODES.md` and `examples/`. Its entry point exports `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`.

1. Add or update the component code. Keep existing node IDs stable.
2. Add a record to `components.json` for a new component, or update that record's `nodes` list. Add the descriptions to the root `node_list.json` and the component's `node_list.json`.
3. Update the full node reference and add a workflow plus actual output to the component's examples. Link the component from the root README and showcase when applicable.
4. Declare common requirements at the root. Keep model-specific or large integrations lazy and document optional installation steps.
5. For a frontend, set `web_entry` to the one registration script in the component's `web/` directory. Import helpers relative to that file. Assets are served at `/msch_nodes/assets/<component>/`; imports to ComfyUI's scripts must resolve from that path. The single root bootstrap loads only active components.
6. Run `python scripts/check_release.py` and `python -m unittest discover -s tests -v`. Load the pack in ComfyUI and exercise the affected nodes before release.
7. Bump the root semantic version in `pyproject.toml`, commit and push, then publish a GitHub release or run **Publish to Comfy Registry**. Verify the uploaded version and Registry status. Never reuse an already published version number.

The root `.comfyignore` excludes showcase media, test fixtures and documentation from Registry archives. GitHub keeps the complete galleries. Existing tests inside each component remain available; some require their component directory on `PYTHONPATH`.
