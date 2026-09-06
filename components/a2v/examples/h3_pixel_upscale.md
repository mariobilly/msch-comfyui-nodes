# H3 Pixel Upscale

Optional second-pass version of h3_generation. Select every required model before running. Both first-pass and refined videos are connected to save nodes. The pixel-upscale branch can require significantly more GPU memory. Included schedule data is verified; H3 inference and pixel refinement have not been executed for this release example.

Load `h3_pixel_upscale.json` on the ComfyUI canvas. `h3_pixel_upscale_api.json` is a prompt for the `/prompt` API, not a canvas workflow. Copy the required files from `inputs/` into `ComfyUI/input/` and reselect them in the load nodes.
