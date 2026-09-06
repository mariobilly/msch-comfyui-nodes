# Unified pack validation

- ComfyUI's actual `load_custom_node` registered all 35 expected node IDs as `custom_nodes.msch-comfyui-nodes`.
- All 15 components loaded without component errors in the local embedded Python 3.12.10 environment.
- All node input schemas were evaluated successfully.
- Six component frontends are served through one root bootstrap; asset-to-ComfyUI import paths are checked.
- Route registration produced no duplicate routes in a clean application.
- The combined Code Matrix implementation rendered a finite 128 × 128 RGB image.
- HTTP checks loaded all six frontend entry points, the Typort editor and font, and the A2V sequencer module.
- Typort rendered a 320 × 180 MP4 using its bundled fonts and browser engine from the new component location.
- Six loader tests cover optional-dependency failure, incomplete registration, legacy-install avoidance, disabled-folder migration, UI-only components and bare test collection.
- All 108 existing A2V core tests pass from their new component location.
- Syntax, JSON workflows, catalog consistency and node-ID uniqueness are checked in GitHub Actions.

Existing component renders and model-specific tests are documented with their examples. Consolidation preserves the implementations; this release does not claim a fresh GPU render of every showcase workflow or every optional model configuration.

The downloaded Registry ZIP was also loaded through ComfyUI and passed the same node, HTTP-asset and typography-render checks. It contains 342 files and is approximately 696 KiB.
