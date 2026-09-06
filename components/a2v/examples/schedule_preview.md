# Schedule Preview

A model-free sequencer/audio preview. Copy inputs/beat.wav to ComfyUI/input. The included schedule has a known synthetic 120 BPM grid and one two-second prompt block; it is authored timing, not a claimed beat-detection result. results/compiled_shot_plan.json is the actual output of the package schedule compiler. No H3 video is represented as rendered in this example.

Load `schedule_preview.json` on the ComfyUI canvas. `schedule_preview_api.json` is a prompt for the `/prompt` API, not a canvas workflow. Copy the required files from `inputs/` into `ComfyUI/input/` and reselect them in the load nodes.
