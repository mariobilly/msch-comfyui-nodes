# Director Renderer

A minimal Director-to-Renderer graph. Uses inputs/demo.png; connect a larger image batch to both nodes for a multi-photo slideshow. The included gallery render uses three frames from the geometric input as three photos. Timeline minimum segment/transition lengths can make a requested very short clip longer than the nominal duration.

Load `director_renderer.json` on the ComfyUI canvas. `director_renderer_api.json` is a prompt for the `/prompt` API, not a canvas workflow. Copy the required files from `inputs/` into `ComfyUI/input/` and reselect them in the load nodes.
