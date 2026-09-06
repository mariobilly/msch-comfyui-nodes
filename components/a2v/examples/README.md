# Example workflows and output results

**[Browse Mario’s showcase](showcase/README.md)** for the new rendered examples and their API workflows. The earlier procedural examples remain below.

Each canvas workflow is a `.json` with a `nodes` array. Files ending `_api.json` are API prompts; send them as the `prompt` field of a `/prompt` request. Supporting timeline/project JSON files are data, not standalone workflows.

Copy the needed files from `inputs/` to `ComfyUI/input/`, then select them in the Load nodes. The geometric scene and synthetic beat are original procedural demo fixtures. Model weights and private media are not included.

## A2V examples

- [Schedule preview](schedule_preview.md): model-free canvas workflow and audio preview.
- [H3 generation template](h3_generation.md): configure model loaders before use.
- [H3 pixel-upscale template](h3_pixel_upscale.md): optional model-dependent refinement.
- [Actual compiled shot-plan result](results/compiled_shot_plan.json). This is schedule data, not a generated video.

## Completed H3 render

The [verified H3 demo](h3_rendered_demo.md) now includes a complete rendered video, still preview, exact workflow and execution details. The earlier compiled-plan result remains a separate model-free example.
