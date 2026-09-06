# MSCH Scan FX: node reference

Stack up to eight thermal, night-vision, hologram, HUD, radar, glitch and other scan effects inside an optional mask.

This reference lists every registered node, required and optional input, current default, allowed range or choices, and output socket. Hidden inputs are supplied by ComfyUI. IMAGE values are batches of RGB float frames; a video needs separate timing/audio unless a native VIDEO socket is used.

## ScanFX

**Display name:** Scan FX (thermal / nightvision / hud / ...)  
**Category:** `ScanFX`  
**Output node:** no

Process each IMAGE frame through eight ordered effect slots, each with its own strength. Choose from the complete effect menu in the input reference. Global mix blends the stack back into the original; an optional MASK, inversion and feathering restrict the affected area. Animated effects use frame position and animation_speed. The scan/depth/thermal appearances are synthetic graphic treatments.

### Required inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `image` | IMAGE | — |  |  |
| `mix` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 | Global opacity of the whole effect stack inside the mask. |
| `mask_feather` | FLOAT | 4.0 | 0.0 to 256.0; step 0.5 | Soften the mask edge (pixels). |
| `invert_mask` | BOOLEAN | False |  |  |
| `animation_speed` | FLOAT | 1.0 | 0.0 to 10.0; step 0.1 | Speed of moving effects (sweep, sonar, ekg, code-rain). |
| `seed` | INT | 0 | 0 to 4294967295 |  |
| `effect_1` | COMBO | thermal | none, thermal, nightvision, xray, lidar, wireframe, holo_sweep, hud, sonar, glitch, hologram, ekg, coderain, chroma, falsecolor, depthmap, sketch, blueprint, halftone, ascii, pixelate, posterize, sobel, bloom, lensflare, vhs, crt, filmgrain, lightpaint, motionblur, slitscan, kaleidoscope, fisheye, tiltshift, doubleexp, solarize, duotone, neon, heathaze, dissolve, voronoi, spectrum, topographic, flowfield, inkbleed, oilpaint, liquidmetal, refraction, caustics, godrays, matrixfloor, vaporwave, aerochrome, uvblacklight, schlieren, bokeh, prism, crosshatch, stipple, frost, teslaarc |  |
| `strength_1` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `effect_2` | COMBO | none | none, thermal, nightvision, xray, lidar, wireframe, holo_sweep, hud, sonar, glitch, hologram, ekg, coderain, chroma, falsecolor, depthmap, sketch, blueprint, halftone, ascii, pixelate, posterize, sobel, bloom, lensflare, vhs, crt, filmgrain, lightpaint, motionblur, slitscan, kaleidoscope, fisheye, tiltshift, doubleexp, solarize, duotone, neon, heathaze, dissolve, voronoi, spectrum, topographic, flowfield, inkbleed, oilpaint, liquidmetal, refraction, caustics, godrays, matrixfloor, vaporwave, aerochrome, uvblacklight, schlieren, bokeh, prism, crosshatch, stipple, frost, teslaarc |  |
| `strength_2` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `effect_3` | COMBO | none | none, thermal, nightvision, xray, lidar, wireframe, holo_sweep, hud, sonar, glitch, hologram, ekg, coderain, chroma, falsecolor, depthmap, sketch, blueprint, halftone, ascii, pixelate, posterize, sobel, bloom, lensflare, vhs, crt, filmgrain, lightpaint, motionblur, slitscan, kaleidoscope, fisheye, tiltshift, doubleexp, solarize, duotone, neon, heathaze, dissolve, voronoi, spectrum, topographic, flowfield, inkbleed, oilpaint, liquidmetal, refraction, caustics, godrays, matrixfloor, vaporwave, aerochrome, uvblacklight, schlieren, bokeh, prism, crosshatch, stipple, frost, teslaarc |  |
| `strength_3` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `effect_4` | COMBO | none | none, thermal, nightvision, xray, lidar, wireframe, holo_sweep, hud, sonar, glitch, hologram, ekg, coderain, chroma, falsecolor, depthmap, sketch, blueprint, halftone, ascii, pixelate, posterize, sobel, bloom, lensflare, vhs, crt, filmgrain, lightpaint, motionblur, slitscan, kaleidoscope, fisheye, tiltshift, doubleexp, solarize, duotone, neon, heathaze, dissolve, voronoi, spectrum, topographic, flowfield, inkbleed, oilpaint, liquidmetal, refraction, caustics, godrays, matrixfloor, vaporwave, aerochrome, uvblacklight, schlieren, bokeh, prism, crosshatch, stipple, frost, teslaarc |  |
| `strength_4` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `effect_5` | COMBO | none | none, thermal, nightvision, xray, lidar, wireframe, holo_sweep, hud, sonar, glitch, hologram, ekg, coderain, chroma, falsecolor, depthmap, sketch, blueprint, halftone, ascii, pixelate, posterize, sobel, bloom, lensflare, vhs, crt, filmgrain, lightpaint, motionblur, slitscan, kaleidoscope, fisheye, tiltshift, doubleexp, solarize, duotone, neon, heathaze, dissolve, voronoi, spectrum, topographic, flowfield, inkbleed, oilpaint, liquidmetal, refraction, caustics, godrays, matrixfloor, vaporwave, aerochrome, uvblacklight, schlieren, bokeh, prism, crosshatch, stipple, frost, teslaarc |  |
| `strength_5` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `effect_6` | COMBO | none | none, thermal, nightvision, xray, lidar, wireframe, holo_sweep, hud, sonar, glitch, hologram, ekg, coderain, chroma, falsecolor, depthmap, sketch, blueprint, halftone, ascii, pixelate, posterize, sobel, bloom, lensflare, vhs, crt, filmgrain, lightpaint, motionblur, slitscan, kaleidoscope, fisheye, tiltshift, doubleexp, solarize, duotone, neon, heathaze, dissolve, voronoi, spectrum, topographic, flowfield, inkbleed, oilpaint, liquidmetal, refraction, caustics, godrays, matrixfloor, vaporwave, aerochrome, uvblacklight, schlieren, bokeh, prism, crosshatch, stipple, frost, teslaarc |  |
| `strength_6` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `effect_7` | COMBO | none | none, thermal, nightvision, xray, lidar, wireframe, holo_sweep, hud, sonar, glitch, hologram, ekg, coderain, chroma, falsecolor, depthmap, sketch, blueprint, halftone, ascii, pixelate, posterize, sobel, bloom, lensflare, vhs, crt, filmgrain, lightpaint, motionblur, slitscan, kaleidoscope, fisheye, tiltshift, doubleexp, solarize, duotone, neon, heathaze, dissolve, voronoi, spectrum, topographic, flowfield, inkbleed, oilpaint, liquidmetal, refraction, caustics, godrays, matrixfloor, vaporwave, aerochrome, uvblacklight, schlieren, bokeh, prism, crosshatch, stipple, frost, teslaarc |  |
| `strength_7` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |
| `effect_8` | COMBO | none | none, thermal, nightvision, xray, lidar, wireframe, holo_sweep, hud, sonar, glitch, hologram, ekg, coderain, chroma, falsecolor, depthmap, sketch, blueprint, halftone, ascii, pixelate, posterize, sobel, bloom, lensflare, vhs, crt, filmgrain, lightpaint, motionblur, slitscan, kaleidoscope, fisheye, tiltshift, doubleexp, solarize, duotone, neon, heathaze, dissolve, voronoi, spectrum, topographic, flowfield, inkbleed, oilpaint, liquidmetal, refraction, caustics, godrays, matrixfloor, vaporwave, aerochrome, uvblacklight, schlieren, bokeh, prism, crosshatch, stipple, frost, teslaarc |  |
| `strength_8` | FLOAT | 1.0 | 0.0 to 1.0; step 0.01 |  |

### Optional inputs

| Input | Type | Default | Range / choices | Details |
|---|---|---|---|---|
| `mask` | MASK | — |  |  |

### Outputs

| Socket | Type |
|---|---|
| `image` | `IMAGE` |
