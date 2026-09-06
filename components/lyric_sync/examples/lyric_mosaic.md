# Lyric Mosaic

Uses inputs/demo.mp4 and inputs/beat.wav, an original synthetic beat track with no singing. The provided result uses evenly distributed fallback timing, not WhisperX vocal alignment. For real lyrics, replace both text and audio and configure WhisperX. Connect PALETTE to palette_in; palette accepts CSV text instead.

Load `lyric_mosaic.json` on the ComfyUI canvas. `lyric_mosaic_api.json` is a prompt for the `/prompt` API, not a canvas workflow. Copy the required files from `inputs/` into `ComfyUI/input/` and reselect them in the load nodes.
