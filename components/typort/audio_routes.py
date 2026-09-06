import asyncio
from pathlib import Path

from aiohttp import web
import folder_paths
from server import PromptServer

from .audio_analysis import analyze

_analysis_slot = asyncio.Semaphore(1)


def input_audio(name):
    if not isinstance(name, str) or not name or len(name) > 2000:
        raise ValueError("Upload an audio file in the studio first.")
    base = Path(folder_paths.get_input_directory()).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError("Audio must be an existing file inside ComfyUI/input.")
    return path


@PromptServer.instance.routes.post("/mariotyport/analyze-audio")
async def analyze_audio(request):
    try:
        data = await request.json()
        if not isinstance(data, dict) or type(data.get("instruments", False)) is not bool:
            raise ValueError("Invalid analysis request.")
        device = data.get("device", "auto")
        if device not in ("auto", "cuda", "cpu"):
            raise ValueError("Separation device must be auto, cuda or cpu.")
        path = input_audio(data.get("file"))
        if _analysis_slot.locked():
            return web.json_response({"error": "An audio analysis is already running. Try again after it finishes."}, status=409)
        async with _analysis_slot:
            result = await asyncio.to_thread(analyze, path, data["file"], data.get("instruments", False),
                                             Path(folder_paths.models_dir) / "mariotyport", device)
        return web.json_response(result)
    except (ValueError, OSError, RuntimeError) as exc:
        return web.json_response({"error": str(exc)}, status=400)
