"""Constrain workflow-controlled paths to a host-configured ComfyUI directory."""
import ntpath
import os
from pathlib import Path


def resolve_path(base, value, *, kind=None):
    """Reject rooted/traversing paths, then check containment after realpath.

    Check both slash styles on every OS so shared workflows cannot carry Windows
    drive/UNC paths or traversal that becomes unsafe on a different host.
    ``kind=None`` permits a not-yet-created output file or directory.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter a path relative to the ComfyUI directory.")
    value = value.strip().replace("\\", "/")
    if (os.path.isabs(value) or ntpath.isabs(value) or ntpath.splitdrive(value)[0]
            or ".." in value.split("/") or ":" in value or "\x00" in value):
        raise ValueError("Paths must be relative; absolute paths and '..' are not allowed.")
    root = os.path.realpath(base)
    resolved = os.path.realpath(os.path.join(root, value))
    try:
        contained = os.path.commonpath([root, resolved]) == root
    except ValueError:
        contained = False
    if not contained:
        raise ValueError("Path escapes the configured ComfyUI directory (including symlinks).")
    path = Path(resolved)
    if kind == "file" and not path.is_file():
        raise FileNotFoundError(f"File not found inside the ComfyUI directory: {value}")
    if kind == "directory" and not path.is_dir():
        raise FileNotFoundError(f"Folder not found inside the ComfyUI directory: {value}")
    return path


def input_path(value, *, kind="file"):
    import folder_paths
    return resolve_path(folder_paths.get_input_directory(), value, kind=kind)


def output_path(value):
    import folder_paths
    return resolve_path(folder_paths.get_output_directory(), value)
