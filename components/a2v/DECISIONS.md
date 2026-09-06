# DECISIONS.md

## 1. Purpose

MschA2V is a beat-synced scheduling/orchestration layer on top of the
already-installed MiniMax H3 ComfyUI pack (`comfyui-minimax-h3-audio-T8`).
MschA2V owns: beat/onset analysis, the beat-grid timeline editor, drift-free
beat→frame conversion, per-block/shot planning, and post-render
fades/crossfades/assembly. The H3 pack owns: the model, its conditioning
format, its frame-length grid, its sampler, and its VAE. Every place MschA2V
touches the H3 pack goes through the single adapter file
`mscha2v/h3/adapter.py` — nothing else in this repo reimplements H3
internals.

## 2. H3 Introspection

The installed pack was read in full (not guessed) at
`E:/ComfyUI_windows_portable/ComfyUI/custom_nodes/comfyui-minimax-h3-audio-T8`
before any code was written. Findings, with exact citations:

- **Joint audio-video latent.** `core.py:72-99` (`empty_av_latent`,
  `nested_av_parts`): a single `comfy.nested_tensor.NestedTensor` holds a
  video tensor `[1,24,latent_t,H/16,W/16]` and an audio tensor
  `[1,32,2,audio_t]`. There is no separate "render video, then attach audio"
  step — H3 always samples both branches of one packed latent together.
  Width/height must be divisible by 32.
- **Frame grid.** `core.py:14-28`: `align_frame_count(n) = max(5,n) +
  ((5-n) % 17)` — a "17n+5" grid. `MIN_TRAINED_FRAMES=124` (~5.17s),
  `MAX_TRAINED_FRAMES=362` (~15.1s), `FPS=24` (fixed), `AUDIO_LATENT_FPS=40`.
  The original brief's guessed rule ("26→39, suggesting a 13-step cadence")
  was **wrong** and is fully superseded by this introspected formula.
- **Audio locking.** `core.py:217-227` (`replace_audio_latent`):
  `denoise_strength=0.0` freezes the audio branch to an exact encoded copy of
  the given audio (used by `audio_mode="lock_source"`); `denoise_strength>0`
  (e.g. 0.35, used by `remix_source`) leaves it partially denoisable.
- **Timing/padding.** `timing.py:33-78` (`make_timing_plan`): pads a short
  requested window up to the model's minimum, centering the pad
  symmetrically around the requested scene (via `warmup_seconds`/
  `cooldown_seconds`/an even split of any remaining "extra" context), and
  returns a `TimingPlan` recording exactly where the real content sits
  inside that padded window (`main_prompt_start_seconds`/
  `main_prompt_end_seconds`) plus a `final_trim_start_seconds`. `timing.py:
  81-92` (`window_audio`) slices+pads a source AUDIO dict to match. Both
  import `torch`/`comfy.*` at module level — not importable from
  `mscha2v/core`.
- **Conditioning.** `conditioning.py:125-149` (`build_conditioning`) builds
  the empty AV latent, encodes the text prompt, and (for `lock_source`/
  `remix_source`) injects the audio into that latent, all in one call.
  Returns `(conditioning, latent, output_audio, conditioned_prompt,
  media_map, report_text)` — **positive conditioning only**; there is no
  built-in negative-conditioning path. `task_type` resolution
  (`conditioning.py:68-90`) supports `i2va`/`fl2va`/`l2va` continuity via
  `first_frame`/`last_frame` IMAGE inputs.
- **Prompt tags.** `prompt_tags.py:25-51` (`prepare_prompt`) canonicalizes
  optional `<Picture N>`/`<Video N>`/`<Audio N>` reference tags and raises
  `ValueError` on an out-of-range ordinal when `strict=True`. Untagged plain
  text passes through completely unchanged. This is only ever invoked deep
  inside `build_conditioning` at render time — never at MschA2V's planning
  layer, so `mscha2v/core/schedule.py` keeps every prompt byte-for-byte.
  Dialogue synthesis uses a **separate** tag family, `<d>[{language}]
  {text}</d>` (lowercase — `speech.py:513-525`), not `<D>...</D>` as the
  original brief guessed; MschA2V never calls `speech.py`/`dialogue_audio.py`.
- **Sampling.** `sampling.py:189-254` (`setup_dual_clock_sampling`) returns
  `(patched_model, sampler, sigmas)` — a **SAMPLER/SIGMAS setup only**, the
  same shape as ComfyUI's native `SamplerCustomAdvanced` path. It takes no
  cfg/positive/negative/seed. "Dual clock" means video and audio are
  denoised on two independent sigma schedules within one packed vector
  (`shift_video`/`shift_audio` reparameterize the audio branch's sigma from
  the video branch's). Per-step progress already exists
  (`comfy.utils.model_trange`); nothing wraps an outer per-shot/per-block
  bar, so `MschA2V_BeatKSampler` adds its own `comfy.utils.ProgressBar`.
- **Decode/trim.** `audio_ops.py:25-40` (`decode_av_latent`) — single-shot,
  full-tensor decode; no tiled decode exists anywhere in the pack (confirmed
  via a full-repo grep for "tile"). `audio_ops.py:107-143`
  (`trim_av_output`) already implements frame/sample-accurate trimming —
  reused directly instead of reimplemented.
- **Preflight.** `preflight.py` (`run_preflight`) validates
  width/height/length/audio_mode/model/vaes/refs before running.
- **No multi-text-prompt-per-latent mechanism exists anywhere in the pack.**
  `multikeyframe_advanced.py`'s "keyframes" are **image** anchors within one
  single-prompt render, not multiple text prompts. The pack's own
  long-video feature (for content beyond `MAX_TRAINED_FRAMES`) always
  renders as multiple separate sequential passes too — autoregressive,
  context-conditioned on the previous segment's tail latent, persisted to
  on-disk safetensors state, orchestrated either node-by-node or via an
  async aiohttp background-job queue across multiple separate ComfyUI graph
  executions (`long_video_background.py`, `long_video_routes.py`) — never
  one shared latent. This directly falsified the original brief's "grouped
  continuous latent with internal `cond_keyframes`" mental model.
- **Node authoring API.** H3's own nodes use the newer V3 `io.ComfyNode`/
  `comfy_entrypoint()` API (`nodes.py:1-46`). MschA2V's 6 nodes use the
  classic V1 API (`INPUT_TYPES`/`RETURN_TYPES`/`FUNCTION`,
  `NODE_CLASS_MAPPINGS`) instead — lower implementation risk, and the two
  interoperate fine since ComfyUI matches graph sockets by type string
  (`MODEL`, `LATENT`, `CONDITIONING`, `VAE`, `CLIP`, `AUDIO`, `IMAGE`, ...),
  not by authoring API.
- **Package naming.** The pack's directory name (`comfyui-minimax-h3-audio-T8`)
  is hyphenated and can't be `import`ed by dotted path. Its own
  `__init__.py:1-19` works around this for standalone test collection by
  registering a synthetic `types.ModuleType` package (with `__path__` set to
  its real directory) in `sys.modules`. `mscha2v/h3/adapter.py` mirrors this
  exact trick to load the pack's submodules, located via a known-name-first
  search, a `*minimax*h3*` glob fallback, and an `MSCHA2V_H3_PACK_DIR`
  environment-variable override.

Additional native ComfyUI APIs verified by reading `comfy/samplers.py`,
`comfy/sample.py`, `comfy/utils.py`, `comfy_extras/nodes_custom_sampler.py`,
`comfy_extras/nodes_audio.py`, and `nodes.py` before writing
`beat_ksampler.py`/`pixel_upscale.py`:

- `comfy.samplers.CFGGuider(model_patcher)` → `.set_conds(positive,
  negative)` → `.set_cfg(cfg)` → `.sample(noise, latent_image, sampler,
  sigmas, denoise_mask=..., seed=...)` returns a raw tensor (not a dict).
  Conditioning is `list[tuple[Tensor|None, dict]]` — exactly what
  `clip.encode_from_tokens_scheduled(tokens)` and H3's `build_conditioning`
  both already return.
- `comfy.sample.prepare_noise(latent_image, seed)` branches on
  `latent_image.is_nested` and calls `.unbind()` — this is exactly the
  protocol `comfy.nested_tensor.NestedTensor` implements, so it works
  transparently on H3's AV latent with no special-casing needed.
- `comfy_extras.nodes_audio.load(filepath)` is a **module-level helper**
  (distinct from the `LoadAudio` node class, which is restricted to
  ComfyUI's `input/` directory) that accepts an arbitrary absolute path —
  used by `mscha2v/nodes/_common.py` so `audio_path` isn't artificially
  restricted to the managed input directory.
- `CFGGuider.sample`'s `denoise_mask` parameter is how a latent's
  `noise_mask` (e.g. `lock_source`'s all-zero audio-branch freeze) actually
  takes effect during sampling — it must be threaded through explicitly, not
  just left on the initial latent dict, or `lock_source` would only affect
  the pre-sampling latent and not survive the actual denoise loop.

## 3. Deviations from the original brief (with rationale)

1. `mscha2v/h3/buckets.json` stores grid **parameters** (`step=17, offset=5,
   min_frames=124, max_frames=362, fps=24, audio_latent_fps=40`), not an
   enumerated length list — the brief's "26→39" guess is superseded by the
   real formula (see §2).
2. `mscha2v/core/buckets.py` cannot import H3's `core.py` (it imports
   `torch`/`comfy.*` at module level), so it is a **documented pure-Python
   mirror** of `align_frame_count`, loading its numeric parameters from
   `mscha2v/h3/buckets.json`. `mscha2v/h3/adapter.py::solve_bucket_via_h3`
   calls the real, live pack function as the runtime authority. Also:
   `solve_bucket` additionally clamps the aligned length up to
   `MIN_TRAINED_FRAMES` (a short block's raw 17n+5-aligned length can still
   be well below the model's trained minimum window).
3. **(Revised — see §5)** `MschA2V_ShotPlanner` owns `clip`/`video_vae`/
   `audio_vae`/`audio` and builds every block's H3 conditioning + starting
   (empty/audio-locked) latent up front, matching a reference MiniMax H3
   beat-sync workflow topology the user showed mid-session (screenshot of a
   third-party tool's graph: its Shot Planner node, not its KSampler, owns
   clip/vae/reference-image inputs). `width`/`height`/`fps_override` are
   therefore genuinely used here (no longer validate-and-discard —
   superseding the original deviation #10's "Known Limitation").
   `MschA2V_BeatKSampler` now takes only `model` + the planner's output +
   standard sampler params.
4. **(Revised — see §5)** Groups render as **independent sequential passes
   per constituent Block** (not per Shot — H3 latents of differing bucket
   lengths can't be merged before decode). The original per-block
   `first_frame` continuity trick (feeding the previous block's last decoded
   frame into the next block's conditioning) was **removed** after it turned
   out to conflict with `add_source_as_reference=True` (see §5's bug
   writeup) and after the reference screenshot showed the "correct" answer
   is simpler: optional **global identity/wardrobe reference images**
   (`ref_image_1`/`ref_image_2` on `MschA2V_ShotPlanner`, applied to every
   block) for character consistency across the whole video, relying on
   shared conditioning + H3's own coherence for within-group continuity
   rather than an inter-block image-passing hack. `shot_plan`'s per-block
   entries still carry `group_id`/`is_group_head`/`is_group_tail`/fade/
   crossfade metadata so `MschA2V_ShotAssembler` hard-concatenates within a
   group and crossfades between different shots exactly as before.
5. `MschA2V_ShotAssembler` hard-concatenates blocks sharing a `group_id` (no
   crossfade — continuity already comes from generation-time conditioning)
   and crossfades only at boundaries between different Shots, using
   `crossfade_frames` read from the **incoming** (later) block at that
   boundary — a documented convention, not explicit in the original brief.
   `mscha2v/core/schedule.py::block_output_ranges` implements the identical
   accounting (crossfade overlap shrinks the cumulative timeline) as pure
   math, shared with `MschA2V_BeatPixelUpscaleKSampler` so both nodes agree
   on where each block lands in the final assembled timeline.
6. `MschA2V_ShotAssembler`'s AUDIO output defaults to a straight pass-through
   of the original loaded song track (never reassembled from decoded
   per-shot generated audio) — sidesteps VAE audio round-trip artifacts and
   inter-shot seams entirely, and is trivially frame-accurate to the source.
   `use_generated_audio: BOOLEAN` (default `False`) exposes a best-effort
   alternative (hard-concatenated decoded segments, no declick).
7. All 6 MschA2V nodes use the classic V1 node API (see §2) — matches the
   original brief's `__init__.py` description and lowers implementation risk
   relative to H3's newer V3 API.
8. Negative conditioning is built **per block/cond_keyframe**, from
   `CondKeyframe.negative` (already part of the frozen `Block`/`CondKeyframe`
   schema), via a plain `clip.tokenize()` + `clip.encode_from_tokens_scheduled()`
   call — not through H3's `build_conditioning`, which returns positive
   conditioning only. An optional `negative_fallback` STRING input on
   `MschA2V_BeatKSampler` is used only when a given block's own `negative`
   is empty.
9. `mscha2v/agent/` is a stub only, never invoked; `speech.py`/
   `dialogue_audio.py` are never called by MschA2V. Prompt text passes
   through untouched, so users *may* embed `<d>[lang]...</d>` dialogue tags
   themselves, with the documented caveat that they have no effect while
   `audio_mode="lock_source"` freezes the audio branch (not enforced, just
   documented in the README's Known Limitations).
10. **(Revised — see §5)** `MschA2V_BeatPixelUpscaleKSampler` now operates
    directly on each block's own stored latent in `shot_plan` (decode →
    pixel-upscale → VAE-**encode** back into H3's latent space → partial
    re-sample reusing the SAME conditioning/seed from the low-res pass),
    instead of re-splitting an already-assembled IMAGE batch via
    `block_output_ranges`. It writes the upscaled block back into
    `shot_plan`, so the exact same `MschA2V_ShotAssembler` node runs again
    downstream for both the low-res preview and the final upscale — no
    separate `image` input needed. `video_vae.encode(...)` is still only
    confirmed by convention, not by direct introspection of the H3 pack's
    VAE wrapper source (see §4) — this session's smoke test validated the
    core pipeline through decode but did not exercise the upscale pass;
    still flagged as unverified.

## 4. Flagged risks / documented assumptions

- `cfg` default is `1.0` (flow-model convention) — user-configurable on both
  `MschA2V_BeatKSampler` and `MschA2V_BeatPixelUpscaleKSampler`.
- `comfy.sample.prepare_noise`'s compatibility with the AV `NestedTensor`
  latent is confirmed by reading `comfy/sample.py` (see §2) — low risk, but
  still worth a first-run smoke test.
- `MschA2V_BeatPixelUpscaleKSampler`'s `vae.encode()` usage on the H3 video
  VAE (deviation #10 above) is the single highest-risk unverified assumption
  in this codebase — validate it empirically before production use.
- `fps` output type is `FLOAT` on all three render-adjacent nodes
  (`MschA2V_ShotAssembler`, `MschA2V_BeatPixelUpscaleKSampler`) — verify
  compatibility with whichever video-combine node (core `SaveVideo` vs
  VideoHelperSuite `VHS_VideoCombine`) it's wired to; both commonly accept a
  FLOAT fps input, but confirm on your ComfyUI version.
- The JS-side beat→frame snapping in `web/sequencer/state.js`
  (`beatsToFrameBoundaries`, `beatToSeconds`, `secondsToBeatIndex`)
  duplicates `mscha2v/core/drift.py`/`mscha2v/core/schedule.py`'s algorithms
  in a second language with no automated cross-check. Accepted gap for this
  release; a shared golden-vector JSON fixture both languages assert against
  would close it.
- Downbeats are approximated as every 4th detected beat
  (`mscha2v/core/beat_analysis.py::analyze_audio`) — librosa has no native
  meter/downbeat detector; this is a 4/4-meter heuristic, not a measured
  fact.

## 5. Live smoke-test findings (this session)

After the initial build, the whole pipeline was wired into a real ComfyUI
workflow against the actual installed H3 checkpoint
(`MiniMax_H3_FL2VA_pruned_int8_convrot.safetensors` + the 4-step turbo LoRA
+ Qwen3-VL CLIP + both VAEs) and submitted via `/prompt`, using real beat
data from `POST /mscha2v/analyze` on a 9.4s test clip (3 blocks: 1 single +
1 group of 2).

- **Path-resolution bug (fixed):** `mscha2v/server/routes.py::
  _resolve_and_validate_path` called `os.path.abspath(path)` directly on a
  relative path like `"2.mp3"` (as returned by `GET /mscha2v/files`),
  resolving it against the ComfyUI **process's cwd** instead of its input
  directory — every relative path was rejected as "not inside an allowed
  ComfyUI directory". Fixed to try the path relative to each allowed root
  first (matching what `mscha2v/nodes/_common.py::resolve_audio_path`
  already did correctly for the node layer), falling back to treating it as
  already-absolute.
- **`task_type` conflict bug (fixed by the restructure above):** the
  original per-block `first_frame` continuity trick hardcoded
  `task_type="i2va"` whenever a group-continuation block had a first_frame
  image, but `add_source_as_reference=True` was *always* also passed —
  H3's `conditioning.py::resolve_task_type` explicitly rejects `i2va` (and
  every other non-auto/ref2va/hybrid task type) combined with reference
  media (`"I2VA cannot include reference media; use Auto or Hybrid"`).
  Passing `task_type="auto"` unmodified would have resolved correctly on
  its own (H3's own `resolve_task_type("auto", first_frame, ..., has_refs=
  True)` already returns `"hybrid"`) — the override was both unnecessary
  and actively wrong. Resolved by removing the `first_frame` mechanism
  entirely per the architecture revision above, rather than patching the
  task-type logic in place.
- **Node graph submitted with zero validation errors** against ComfyUI's
  `/prompt` type-checker both before and after the fix, confirming the
  socket types (`MODEL`/`CLIP`/`VAE`/`AUDIO`/custom `MSCHA2V_*` types) line
  up correctly end to end.
- **Confirmed working:** the `mscha2v/h3/adapter.py` dynamic-import loader
  (the synthetic-package trick for the hyphenated H3 pack directory)
  successfully loads the real installed pack and its live constants
  (`FPS=24, AUDIO_LATENT_FPS=40, MIN_TRAINED_FRAMES=124, MAX_TRAINED_FRAMES=
  362`) match the introspected values exactly; all 7 node classes register
  correctly via the root `__init__.py`'s try/except-guarded aggregation.
- **End-to-end success (restructured architecture):** after the fixes above,
  the full chain — `UNETLoader`+`LoraLoaderBypassModelOnly`+`CLIPLoader`+2×
  `VAELoader` → `MschA2V_BeatPromptSequencer` → `MschA2V_ShotPlanner` →
  `MschA2V_BeatKSampler` → `MschA2V_ShotAssembler` → `VHS_VideoCombine` —
  rendered successfully against the real installed H3 checkpoint, producing
  a playable MP4 with beat-synced audio (1 single block + 1 group of 2
  hard-concatenated blocks, ~9.4s test clip). `comfy.sample.prepare_noise`
  on the AV `NestedTensor` latent, `CFGGuider.sample` with
  `denoise_mask=noise_mask` for `lock_source`, and `decode_av_latent` all
  confirmed working end-to-end. **Not yet exercised:**
  `MschA2V_BeatPixelUpscaleKSampler`'s `vae.encode()` path (deviation #10) —
  still the single remaining unverified assumption in this codebase.
