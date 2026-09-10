# Workflow security boundaries

PuppetFace video input, Typort video/audio input, Slideshow image folders,
soundtracks and custom fonts, and A2V audio paths must be relative to the
host-configured ComfyUI input directory. For example, use `clips/demo.mp4` for
`ComfyUI/input/clips/demo.mp4`. There is no working-directory fallback.

The shared resolver rejects absolute paths (including Windows drive and UNC
paths), `..` components, and paths whose `realpath` escapes the configured base
according to `commonpath`. Slideshow also checks individual image entries so a
symlink inside an allowed folder cannot expose a file outside input.
PuppetFace filename prefixes are relative to ComfyUI/output and use the same
validation; nested prefixes such as `project/clip` are supported.

WhisperX is resolved using the fixed command name `whisperx` on the host PATH,
with a known per-user Python 3.13 installation fallback. The legacy
`whisperx_exe` widget is retained for workflow compatibility but ignored, as is
the low-level runner's legacy `exe` argument.

Typort loads the pinned official HTDemucs checkpoint with `weights_only=True`.
Its SHA-256 is verified against the exact in-memory bytes being deserialized.
Only the fixed metadata types required by that artifact are allowlisted within
the restricted load; there is no unrestricted pickle fallback or file-derived
allowlist. Both the checksum and restricted unpickler reject crafted files.

Run `python -m unittest discover -s tests -v` for path, executable and loader
regressions. Runtime tests additionally exercise the affected node entry points,
video read/write and a malicious checkpoint when the optional media dependencies
are installed. Set `MSCH_DEMUCS_CHECKPOINT` to the official checkpoint to verify
full model reconstruction. Symlink tests require a host that permits symlinks.
