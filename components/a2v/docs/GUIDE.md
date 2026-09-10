> Earlier usage guide. See [the current README](../README.md) for installation and scope, and [the node reference](NODES.md) for the complete current interface. Old machine-specific paths must be replaced for your installation.

# ComfyUI-MschA2V

Audio-beat-synced prompt sequencer for **MiniMax H3**, running locally
(int8, via the [comfyui-minimax-h3-audio-T8](https://github.com/T8mars)
pack). Load a song, let the sequencer detect beats/onsets/BPM, author
prompts inside draggable beat-snapped time blocks, and render through H3 in
beat-perfect sync — as independent clips (crossfaded) or as visually
continuous groups — with a local pixel-upscale second pass so a fast
low-resolution timing pass can be pushed to a final 1024–1920px render
without a closed 2K refiner.

MschA2V targets **MiniMax H3 only**. See `DECISIONS.md` for the full
"H3 Introspection" writeup this pack is built on, and every deviation from
the original design brief with its rationale.

## Install

1. Make sure `comfyui-minimax-h3-audio-T8` is installed and its model/VAE
   checkpoints are loadable in your ComfyUI (MschA2V is an orchestration
   layer on top of it, not a replacement).
2. Drop this repo into `ComfyUI/custom_nodes/ComfyUI-MschA2V`.
3. Install the extra Python dependencies into the **same** Python
   environment ComfyUI runs with (the embedded portable build's
   `python_embeded/python.exe`, or your venv):
   ```
   python -m pip install -r requirements.txt
   ```
4. Restart ComfyUI. The six `MschA2V_*` nodes appear under the `MschA2V`
   category.

## Workflow chain

Load the H3 checkpoint the same way the H3 pack's own example workflows do
— it ships no loader nodes of its own, just stock ComfyUI ones:
`UNETLoader` → `LoraLoaderBypassModelOnly` (4-step turbo LoRA) → `model`;
`CLIPLoader` (`type="minimax"`) → `clip`; two `VAELoader`s (video + audio)
→ `video_vae`/`audio_vae`.

```
MschA2V_BeatPromptSequencer
        │  (SCHEDULE, AUDIO, BPM, total_frames)
        ▼
MschA2V_ShotPlanner  ← clip, video_vae, audio_vae, audio  (+ optional ref_image_1/2)
        │  (shot_plan: conditioning + starting latents built per block)
        ▼
MschA2V_BeatKSampler  ← model  (only)
        │  (shot_plan: sampled latents)
        ▼
MschA2V_ShotAssembler  ← video_vae, audio_vae, audio
        │  (IMAGE, AUDIO, fps)
        ▼
   [optional] MschA2V_BeatPixelUpscaleKSampler  ← model, video_vae, audio_vae
        │  (shot_plan: upscaled + re-sampled latents)
        ▼
   MschA2V_ShotAssembler again  ← video_vae, audio_vae, audio
        │  (IMAGE, AUDIO, fps)
        ▼
   VideoHelperSuite "Video Combine" / core "Save Video"
```

`clip`/`video_vae`/`audio_vae`/`audio` all live on **`MschA2V_ShotPlanner`**,
not the sampler — it builds every block's H3 conditioning and starting
(empty/audio-locked) latent up front, so `MschA2V_BeatKSampler` only ever
needs `model` plus standard sampler params. This mirrors how the underlying
H3 pack itself splits conditioning-building from sampling
(`MiniMaxH3AudioConditioningT8` vs `MiniMaxH3DualClockSamplerT8`), and keeps
`MschA2V_BeatPixelUpscaleKSampler` simple: it re-decodes/upscales/re-encodes
each block's *own* stored latent directly and writes it back into the same
`shot_plan` object, so the exact same `MschA2V_ShotAssembler` node runs
again downstream for both the low-res preview and the final upscale — no
separate image-resplitting step needed.

1. **MschA2V_BeatPromptSequencer** — set `audio_path` (a file under
   ComfyUI's `input/` directory; absolute paths and `..` are rejected), click **Open
   Sequencer**, author your blocks, click **Done**. Outputs `SCHEDULE`,
   `AUDIO`, `BPM`, `total_frames`.
2. **MschA2V_ShotPlanner** — compiles the `SCHEDULE` into frame-accurate
   shots (drift-corrected boundaries, grouped shots, H3 bucket lengths) and
   builds each block's positive/negative conditioning + starting AV latent
   (`audio_mode="lock_source"` by default, so the exact song audio drives
   both the model's audio-conditioning reference and stays frozen in the
   latent). Optional `ref_image_1`/`ref_image_2` apply a consistent
   character/wardrobe reference across every block.
3. **MschA2V_BeatKSampler** — samples every block's pre-built latent through
   H3. Reports per-block progress.
4. **MschA2V_ShotAssembler** — decodes, trims padding, applies fades, hard-
   concatenates within groups, crossfades between shots, and asserts the
   final frame count matches the schedule. `AUDIO` output is always the
   original loaded track (see Known Limitations).
5. **MschA2V_BeatPixelUpscaleKSampler** *(optional second pass)* — decodes
   each block's own stored latent, pixel-upscales it, VAE-encodes it back
   into H3's latent space, and partially re-samples with the same
   conditioning/seed as the low-res pass — then feed the result into a
   second `MschA2V_ShotAssembler` to get the final IMAGE/AUDIO.

## Low-res-first workflow

Beat timing math is entirely resolution-independent. For a multi-minute
track, prototype at **288×512** (fast, cheap, lets you iterate on block
placement/prompts/grouping quickly) and only run the full-resolution
`MschA2V_BeatPixelUpscaleKSampler` pass once the timing and prompts are
locked. Both passes operate on the *same* `shot_plan` object, so block
boundaries never drift between the two resolutions.

## Editing `mscha2v/h3/buckets.json`

If a future MiniMax H3 checkpoint changes the valid frame-length grid, edit
`mscha2v/h3/buckets.json`:

```json
{
  "step": 17,
  "offset": 5,
  "min_frames": 124,
  "max_frames": 362,
  "fps": 24,
  "audio_latent_fps": 40
}
```

`mscha2v/core/buckets.py` uses these values for offline planning (and for
`pytest`, which runs without ComfyUI/the H3 pack installed at all);
`mscha2v/h3/adapter.py::solve_bucket_via_h3` cross-checks against the
*live* installed pack's own `align_frame_count`/`MIN_TRAINED_FRAMES`/
`MAX_TRAINED_FRAMES` at render time, so a stale `buckets.json` won't
silently produce wrong renders — only a stale offline preview.

## Known Limitations

- **Grouped-shot continuity relies on shared conditioning, not H3's native
  context-chaining.** Blocks inside a group are still rendered as
  independent sequential H3 passes (H3 latents of differing bucket lengths
  can't be merged before decode) and hard-concatenated with no crossfade at
  assembly. Continuity comes from consistent prompts/character-reference
  images (`ref_image_1`/`ref_image_2` on `MschA2V_ShotPlanner`) and H3's own
  coherence, not from H3's long-video autoregressive context-chaining (which
  this pack deliberately avoids — see `DECISIONS.md` deviation #4 for why).
- **`MschA2V_ShotAssembler`'s `AUDIO` output is the original track by
  default**, not reassembled from decoded generated audio — set
  `use_generated_audio=True` for a best-effort alternative (hard-
  concatenated, no declick between segments).
- **Phase-2 reference-scheduling fields** (`Block.ref_image_slot`,
  `Block.ref_audio_slot`) are present in the schema and the Inspector UI
  (marked "reserved") but are **inert** — nothing reads them yet. See
  `mscha2v/agent/README.md` for the planned Phase-2 natural-language agent
  that will use them.
- **Dialogue tags (`<d>[lang]...</d>`) and `audio_mode="lock_source"` don't
  mix.** `lock_source` freezes the audio branch, so any dialogue-synthesis
  instructions in a prompt have no audible effect while it's active. Use
  `remix_source` or `native` if you want H3 to actually synthesize dialogue.
- **`MschA2V_BeatPixelUpscaleKSampler`'s VAE-encode step is unverified.**
  It assumes H3's video VAE wrapper exposes a standard `.encode()` alongside
  its confirmed `.decode()`. Validate this against your actual H3 checkpoint
  before relying on the upscale pass in production — see `DECISIONS.md` §4.
- No tiled decode exists anywhere in the underlying H3 pack, so very large
  frame batches decode as one full-tensor operation — watch VRAM at high
  resolutions/long groups.
- `MschA2V_ShotPlanner`'s `width`/`height` are validated but not carried
  into the `SHOT_PLAN` schema — keep them consistent with
  `MschA2V_BeatKSampler`'s own `width`/`height` inputs by hand.

## Tests

```
python -m pytest tests -v
python -m ruff check mscha2v tests
```

Both run with **no ComfyUI install and no GPU** — `mscha2v/core/*.py` has
zero `comfy`/`torch` imports (mechanically enforced by
`tests/test_no_comfy_imports.py`).

## License

MIT.
