"""aiohttp route handlers for the MschA2V sequencer frontend.

Imported (and its routes registered as a module-level side effect) from
mscha2v/__init__.py inside a try/except guard, so a broken/absent ComfyUI
server import never prevents `mscha2v.core`/`mscha2v.h3` from being
pytest-importable on their own.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import OrderedDict

from aiohttp import web
from server import PromptServer

from ..core import beat_analysis, schemas

logger = logging.getLogger(__name__)

_ANALYZE_CACHE: dict[tuple, dict] = {}
_WAVEFORM_CACHE: OrderedDict[tuple, list] = OrderedDict()
_WAVEFORM_CACHE_MAX = 200

_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi"}


def _allowed_roots() -> list[str]:
    import folder_paths

    roots = []
    for getter in (folder_paths.get_input_directory, folder_paths.get_output_directory):
        try:
            roots.append(os.path.abspath(getter()))
        except Exception:
            pass
    return roots


def _resolve_and_validate_path(path: str) -> str:
    """Resolve `path` to an absolute path and verify it sits inside one of
    ComfyUI's input/output directories -- rejects path traversal.

    `path` is normally a relative path as returned by GET /mscha2v/files
    (relative to the input/output directory it was listed from), so each
    candidate is tried relative to every allowed root FIRST, falling back to
    treating it as already-absolute -- not `os.path.abspath(path)` alone,
    which would resolve a bare relative path against the server process's
    cwd instead of ComfyUI's managed directories.
    """
    if not path:
        raise ValueError("path is required")
    roots = _allowed_roots()
    candidates = [os.path.abspath(os.path.join(root, path)) for root in roots]
    candidates.append(os.path.abspath(path))

    for abspath in candidates:
        for root in roots:
            try:
                if os.path.commonpath([abspath, root]) != root:
                    continue
            except ValueError:
                continue  # different drive on Windows -> commonpath raises
            if os.path.isfile(abspath):
                return abspath
    raise FileNotFoundError(
        f"file not found: {path!r} (checked under {roots!r} and as an absolute path)"
    )


def _error_response(exc: Exception) -> web.Response:
    if isinstance(exc, FileNotFoundError):
        status = 404
    elif isinstance(exc, (ValueError, PermissionError)):
        status = 400
    else:
        status = 500
    return web.json_response({"error": str(exc)}, status=status)


def register_routes() -> None:
    routes = PromptServer.instance.routes

    @routes.post("/mscha2v/analyze")
    async def analyze(request: web.Request) -> web.Response:
        try:
            body = await request.json()
            path = body.get("path", "")
            source = body.get("source", "full")
            resolved = _resolve_and_validate_path(path)
            mtime = os.path.getmtime(resolved)
            cache_key = (resolved, mtime, source)
            cached = _ANALYZE_CACHE.get(cache_key)
            if cached is not None:
                return web.json_response(cached)
            beat_map = await asyncio.to_thread(beat_analysis.analyze_audio, resolved, source)
            payload = schemas.beat_map_to_dict(beat_map)
            _ANALYZE_CACHE[cache_key] = payload
            return web.json_response(payload)
        except Exception as exc:
            if not isinstance(exc, (ValueError, FileNotFoundError, PermissionError)):
                logger.exception("MschA2V /mscha2v/analyze failed")
            return _error_response(exc)

    @routes.get("/mscha2v/waveform")
    async def waveform(request: web.Request) -> web.Response:
        try:
            path = request.query.get("path", "")
            px = max(64, min(8000, int(request.query.get("px", "2000"))))
            resolved = _resolve_and_validate_path(path)

            t0 = float(request.query.get("t0", "0"))
            t1_raw = request.query.get("t1")
            if t1_raw is None:
                import soundfile as sf

                info = sf.info(resolved)
                t1 = info.frames / float(info.samplerate)
            else:
                t1 = float(t1_raw)

            cache_key = (resolved, os.path.getmtime(resolved), px, round(t0, 2), round(t1, 2))
            cached = _WAVEFORM_CACHE.get(cache_key)
            if cached is not None:
                _WAVEFORM_CACHE.move_to_end(cache_key)
                return web.json_response({"peaks": cached})

            peaks = await asyncio.to_thread(beat_analysis.downsample_waveform_peaks, resolved, px, t0, t1)
            _WAVEFORM_CACHE[cache_key] = peaks
            _WAVEFORM_CACHE.move_to_end(cache_key)
            while len(_WAVEFORM_CACHE) > _WAVEFORM_CACHE_MAX:
                _WAVEFORM_CACHE.popitem(last=False)
            return web.json_response({"peaks": peaks})
        except Exception as exc:
            if not isinstance(exc, (ValueError, FileNotFoundError, PermissionError)):
                logger.exception("MschA2V /mscha2v/waveform failed")
            return _error_response(exc)

    @routes.get("/mscha2v/files")
    async def files(request: web.Request) -> web.Response:
        try:
            import folder_paths

            which = request.query.get("dir", "input")
            ext_filter = request.query.get("ext", "audio")
            root = folder_paths.get_output_directory() if which == "output" else folder_paths.get_input_directory()
            if ext_filter == "audio":
                allowed_exts = _AUDIO_EXTENSIONS
            elif ext_filter == "video":
                allowed_exts = _VIDEO_EXTENSIONS
            else:
                allowed_exts = _AUDIO_EXTENSIONS | _VIDEO_EXTENSIONS

            def _list_files() -> list[dict]:
                results = []
                for dirpath, _dirnames, filenames in os.walk(root):
                    for name in filenames:
                        if os.path.splitext(name)[1].lower() not in allowed_exts:
                            continue
                        full = os.path.join(dirpath, name)
                        try:
                            stat = os.stat(full)
                        except OSError:
                            continue
                        rel = os.path.relpath(full, root).replace(os.sep, "/")
                        results.append({"path": rel, "mtime": stat.st_mtime, "size": stat.st_size})
                results.sort(key=lambda r: r["path"])
                return results

            results = await asyncio.to_thread(_list_files)
            return web.json_response(results)
        except Exception as exc:
            logger.exception("MschA2V /mscha2v/files failed")
            return _error_response(exc)


register_routes()
