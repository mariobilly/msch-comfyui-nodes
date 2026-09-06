# Migrate to one MSCH Nodes pack

The former separate repositories are superseded by **MSCH Nodes** (`msch-comfyui-nodes`). The new pack keeps all 35 existing node IDs, input/output definitions and display names.

1. Save your workflows and stop ComfyUI. Back up any personal files you stored inside the old node folders.
2. In Manager, uninstall or disable the old MSCH packages listed below. For a manual installation, move those folders outside every `custom_nodes` directory, or rename each folder with a `.disabled` suffix.
3. Install `https://github.com/mariobilly/msch-comfyui-nodes` through Manager, or clone it into `ComfyUI/custom_nodes` and install the root `requirements.txt` with ComfyUI's Python.
4. Restart ComfyUI and refresh the browser. Open your existing workflows; the node IDs and links remain the same. Save workflows again so current package metadata can be recorded.

Do not remove the separately installed MiniMax H3 integration, VideoHelperSuite, model files or source media used by your workflows.

## Old folders replaced by this pack

- `msch-a2v`
- `msch-code-matrix`
- `msch-edge-ascii`
- `msch-lyric-sync`
- `msch-mcp-bridge`
- `msch-pointillism`
- `msch-puppet-face`
- `msch-scanfx`
- `msch-slideshow`
- `msch-slideshow-forge`
- `msch-synkitfx`
- `msch-theme`
- `msch-timeslice`
- `msch-typort`
- `msch-warp-wiggle`

Older `marioslideshow` and `mariotyport` folders are recognized too. If you renamed a legacy folder to a different active name, disable that copy manually.

## If both installations are present

The unified loader detects the known old folders before importing a component. It leaves that component to the existing installation and logs a migration notice. Its frontend is also skipped, avoiding duplicate route and extension registrations. After the old folder is disabled and ComfyUI restarts, the unified pack takes over that component.

This compatibility behavior does not uninstall, rename or delete anything automatically. It is a transition aid; the intended final installation is one `msch-comfyui-nodes` folder.

Old Registry records and cached Manager entries can remain visible during the transition. Use the unified package for new installs. Historical repositories remain available for existing links and rollback.
