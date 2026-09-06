# MSCH Puppet Face showcase

Examples supplied by Mario from the MSCH Node Showcase collection. The output files are preserved as supplied.

![Featured example](outputs/mesh_track_mouth_00000_preview.jpg)

The viral point-and-click face-puppet look: a tracked landmark mesh plus an animated mouse cursor over face frames. Load Video / Overlay / Save Video nodes.

- mesh_track_mouth.mp4 - all landmark dots + mesh lines, cursor tracks the mouth with a grab ring
- contours_sweep_cursor.mp4 - contour dots in acid green, cursor sweeps across the frame

## Gallery

Click a video preview to open its file on GitHub, or use the download link.

### Contours sweep cursor

[![Contours sweep cursor](outputs/contours_sweep_cursor_00000_preview.jpg)](outputs/contours_sweep_cursor_00000.mp4)

[Open MP4](outputs/contours_sweep_cursor_00000.mp4) · [Download original](https://github.com/mariobilly/msch-comfyui-nodes/raw/refs/heads/main/components/puppet_face/examples/showcase/outputs/contours_sweep_cursor_00000.mp4)

### Mesh track mouth

[![Mesh track mouth](outputs/mesh_track_mouth_00000_preview.jpg)](outputs/mesh_track_mouth_00000.mp4)

[Open MP4](outputs/mesh_track_mouth_00000.mp4) · [Download original](https://github.com/mariobilly/msch-comfyui-nodes/raw/refs/heads/main/components/puppet_face/examples/showcase/outputs/mesh_track_mouth_00000.mp4)

## API workflows

These JSON files are ComfyUI API prompts, not canvas-format workflows. Send one as the `prompt` field of a `/prompt` request, or use a tool that accepts API workflows. A canvas importer may require conversion.

Choose your own source media and installed models before running. Source photos, video clips, audio and model weights are not bundled in this showcase. The supplied render settings and connections are retained; machine-specific absolute paths in the API copies use `INPUT_ROOT/` or `LOCAL_FILES/` placeholders. Replace these with paths valid on your computer.

- [puppet_face_api.json](workflows_api/puppet_face_api.json): `PuppetFaceLoadVideo`, `PuppetFaceOverlay`, `PuppetFaceSaveVideo`.

### Input files and models

| Workflow | Node | Input | Source selection |
|---|---|---|---|
| `puppet_face_api.json` | `1` | `video` | `msch_face.mp4` |

## Source notes

The collection notes identify images from the Jim Morrison image library, Mario’s clips, and the Suno track “Crushing Syncopation”. Those source assets are not included separately. The rendered media is supplied as showcase material; the repository’s MIT license describes the node code and does not establish a separate license for underlying media.
