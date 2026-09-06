# Example workflows and output results

**[Browse Mario’s showcase](showcase/README.md)** for the new rendered examples and their API workflows. The earlier procedural examples remain below.

Each canvas workflow is a `.json` with a `nodes` array. Files ending `_api.json` are API prompts; send them as the `prompt` field of a `/prompt` request. Supporting timeline/project JSON files are data, not standalone workflows.

Copy the needed files from `inputs/` to `ComfyUI/input/`, then select them in the Load nodes. The geometric scene and synthetic beat are original procedural demo fixtures. Model weights and private media are not included.

- [demo](<demo.md>)

## Rendered results

- [demo video](results/demo.mp4) · [still preview](results/demo.png) · [render record](results/demo.json)

The included files are actual outputs from invoking the package code in the installed ComfyUI Python environment. Gallery encoding uses H.264 at 12 FPS. Small visual differences are possible across fonts, library versions and hardware. The render records state any fallback behavior.
