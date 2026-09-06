# MSCH A2V: node reference

Beat-synced prompt sequencing, shot planning, MiniMax H3 sampling, assembly and pixel upscaling for music videos.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## MschA2V_BeatPromptSequencer

**Display name:** MschA2V Beat Prompt Sequencer  
**Category:** `MschA2V`  
**Output node:** no

Open the browser sequencer to author beat-snapped prompt blocks and compile the saved schedule. Outputs MSCHA2V_SCHEDULE, total frame count, the matching audio window and BPM. schedule_json stores the editable timeline in the workflow. Audio start/duration overrides and an optional compiled plan can select a particular render window.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `audio_path` | STRING |  |  |  |
| `schedule_json` | STRING | {} |  |  Multiline text is supported. |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `audio_start_seconds` | FLOAT | -1.0 | -1.0 to 100000.0; step 0.01 |  |
| `audio_duration_seconds` | FLOAT | -1.0 | -1.0 to 100000.0; step 0.01 |  |

### Outputs

| Socket | Type |
|---|---|
| `prompt_schedule` | `MSCHA2V_SCHEDULE` |
| `total_frames` | `INT` |
| `audio` | `AUDIO` |
| `bpm` | `FLOAT` |

## MschA2V_LoadAudioPath

**Display name:** MschA2V Load Audio Path  
**Category:** `MschA2V`  
**Output node:** no

Decode an audio path into ComfyUI AUDIO and report its duration. Optional gain changes the waveform level. Use this to feed the sampler workflow or audition source material; the node accepts local filesystem paths and needs the file to exist on the machine running ComfyUI.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `audio_path` | STRING |  |  |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `gain_db` | FLOAT | 0.0 | -60.0 to 24.0; step 0.1 |  |

### Outputs

| Socket | Type |
|---|---|
| `audio` | `AUDIO` |
| `duration_seconds` | `FLOAT` |

## MschA2V_PreviewAudio

**Display name:** MschA2V Preview Audio  
**Category:** `MschA2V`  
**Output node:** yes

Write a temporary playable audio preview for a connected AUDIO value. This is an output node with no data sockets on its output side. It lets you audition the selected timeline window before committing GPU time to video generation.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `audio` | AUDIO | — |  |  |

### Outputs

| Socket | Type |
|---|---|
| UI preview only | No data outputs |

## MschA2V_ShotPlanner

**Display name:** MschA2V Shot Planner  
**Category:** `MschA2V`  
**Output node:** no

Convert the prompt schedule into MiniMax H3 shot conditioning and starting latents using the CLIP encoder, video VAE, audio VAE and timeline audio. Set output dimensions, master seed, audio/task mode and optional reference inputs. Outputs MSCHA2V_SHOT_PLAN for the beat sampler; planning requires compatible H3 components and is not a generic model adapter.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `prompt_schedule` | MSCHA2V_SCHEDULE | — |  |  |
| `clip` | CLIP | — |  |  |
| `vae` | VAE | — |  |  |
| `audio_vae` | VAE | — |  |  |
| `timeline_audio` | AUDIO | — |  |  |
| `master_seed` | INT | 0 | 0 to 4294967295 |  |
| `width` | INT | 768 | 32 to 1920; step 32 |  |
| `height` | INT | 768 | 32 to 1920; step 32 |  |
| `fps_override` | INT | 0 | 0 to 60 |  |
| `audio_mode` | COMBO | lock_source | lock_source, remix_source, native |  |
| `task_type` | COMBO | auto | auto, t2va, i2va, fl2va, l2va, ref2va, hybrid |  |
| `add_source_as_reference` | BOOLEAN | True |  |  |
| `ref_image_size` | COMBO | match | match, max |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `negative_fallback` | STRING |  |  |  Multiline text is supported. |
| `ref_image_0` | IMAGE | — |  |  |
| `ref_image_1` | IMAGE | — |  |  |
| `ref_image_2` | IMAGE | — |  |  |
| `ref_video_0` | IMAGE | — |  |  |
| `ref_video_audio_0` | AUDIO | — |  |  |
| `ref_audio_0` | AUDIO | — |  |  |

### Outputs

| Socket | Type |
|---|---|
| `shot_plan` | `MSCHA2V_SHOT_PLAN` |

## MschA2V_BeatKSampler

**Display name:** MschA2V Beat KSampler  
**Category:** `MschA2V`  
**Output node:** no

Sample each planned MiniMax H3 shot using the connected model. Steps, video/audio shifts, sampler, scheduler, CFG, denoise and seed control generation. Outputs MSCHA2V_LATENTS containing the per-shot results and timing context for assembly or a pixel-upscale pass.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `model` | MODEL | — |  |  |
| `shot_plan` | MSCHA2V_SHOT_PLAN | — |  |  |
| `steps` | INT | 4 | 1 to 1000 |  |
| `shift_video` | FLOAT | 12.0 | 0.01 to 100.0; step 0.01 |  |
| `shift_audio` | FLOAT | 3.0 | 0.01 to 100.0; step 0.01 |  |
| `sampler_name` | COMBO | dual_clock_euler | dual_clock_euler, euler, euler_cfg_pp, euler_ancestral, euler_ancestral_cfg_pp, heun, heunpp2, exp_heun_2_x0, exp_heun_2_x0_sde, dpm_2, dpm_2_ancestral, lms, dpm_fast, dpm_adaptive, dpmpp_2s_ancestral, dpmpp_2s_ancestral_cfg_pp, dpmpp_sde, dpmpp_sde_gpu, dpmpp_2m, dpmpp_2m_cfg_pp, dpmpp_2m_sde, dpmpp_2m_sde_gpu, dpmpp_2m_sde_heun, dpmpp_2m_sde_heun_gpu, dpmpp_3m_sde, dpmpp_3m_sde_gpu, ddpm, lcm, ipndm, ipndm_v, deis, res_multistep, res_multistep_cfg_pp, res_multistep_ancestral, res_multistep_ancestral_cfg_pp, gradient_estimation, gradient_estimation_cfg_pp, er_sde, seeds_2, seeds_3, sa_solver, sa_solver_pece, ddim, uni_pc, uni_pc_bh2 |  |
| `scheduler` | COMBO | native_flow | native_flow, beta57, simple, sgm_uniform, karras, exponential, ddim_uniform, beta, normal, linear_quadratic, kl_optimal |  |
| `cfg` | FLOAT | 1.0 | 0.0 to 30.0; step 0.1 |  |
| `denoise` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `seed` | INT | 0 | 0 to 4294967295 |  |

### Outputs

| Socket | Type |
|---|---|
| `latents` | `MSCHA2V_LATENTS` |

## MschA2V_ShotAssembler

**Display name:** MschA2V Shot Assembler  
**Category:** `MschA2V`  
**Output node:** no

Decode sampled per-shot latents with the video VAE and assemble them into an IMAGE sequence using the plan's timing and overlap behavior. Connect output images and the sequencer's audio to a video encoder. This node returns video frames only.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `latents` | MSCHA2V_LATENTS | — |  |  |
| `vae` | VAE | — |  |  |

### Outputs

| Socket | Type |
|---|---|
| `images` | `IMAGE` |

## MschA2V_BeatPixelUpscaleKSampler

**Display name:** MschA2V Beat Pixel Upscale KSampler  
**Category:** `MschA2V`  
**Output node:** no

Run an optional pixel-space refinement pass over sampled shots: decode, resize toward target_long_side, re-encode with the VAE and resample against the shot plan. Upscale method and denoise set the balance between preserving the first pass and generating detail. Returns MSCHA2V_LATENTS for the same Shot Assembler. Higher resolutions increase GPU memory and runtime.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `model` | MODEL | — |  |  |
| `shot_plan` | MSCHA2V_SHOT_PLAN | — |  |  |
| `latent` | MSCHA2V_LATENTS | — |  |  |
| `vae` | VAE | — |  |  |
| `target_long_side` | INT | 1024 | 512 to 1920; step 32 |  |
| `upscale_method` | COMBO | lanczos | lanczos, bicubic, bilinear, nearest-exact |  |
| `steps` | INT | 40 | 1 to 1000 |  |
| `cfg` | FLOAT | 1.0 | 0.0 to 30.0; step 0.1 |  |
| `denoise` | FLOAT | 0.75 | 0.0 to 1.0; step 0.01 |  |
| `seed` | INT | 0 | 0 to 4294967295 |  |
| `sampler_name` | COMBO | dual_clock_euler | dual_clock_euler, euler, euler_cfg_pp, euler_ancestral, euler_ancestral_cfg_pp, heun, heunpp2, exp_heun_2_x0, exp_heun_2_x0_sde, dpm_2, dpm_2_ancestral, lms, dpm_fast, dpm_adaptive, dpmpp_2s_ancestral, dpmpp_2s_ancestral_cfg_pp, dpmpp_sde, dpmpp_sde_gpu, dpmpp_2m, dpmpp_2m_cfg_pp, dpmpp_2m_sde, dpmpp_2m_sde_gpu, dpmpp_2m_sde_heun, dpmpp_2m_sde_heun_gpu, dpmpp_3m_sde, dpmpp_3m_sde_gpu, ddpm, lcm, ipndm, ipndm_v, deis, res_multistep, res_multistep_cfg_pp, res_multistep_ancestral, res_multistep_ancestral_cfg_pp, gradient_estimation, gradient_estimation_cfg_pp, er_sde, seeds_2, seeds_3, sa_solver, sa_solver_pece, ddim, uni_pc, uni_pc_bh2 |  |
| `scheduler` | COMBO | native_flow | native_flow, beta57, simple, sgm_uniform, karras, exponential, ddim_uniform, beta, normal, linear_quadratic, kl_optimal |  |

### Outputs

| Socket | Type |
|---|---|
| `latent` | `MSCHA2V_LATENTS` |
