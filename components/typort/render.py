"""Frame-at-a-time Chromium typography, with bounded-memory FFmpeg export."""
import base64
import io
import json
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .project import FONTS, FORMATS, validate_project
from .audio_analysis import decode, fingerprint


def prepare_soundtrack(track, source, duration, destination):
    if track["analysis"] and fingerprint(source) != track["analysis"]["fingerprint"]:
        raise ValueError("The soundtrack file changed. Analyze it again before rendering.")
    rate = 48000
    audio = decode(source, rate=rate, stereo=True)
    begin, end = round(track["trim_start"] * rate), min(audio.shape[1], round(track["trim_end"] * rate))
    frames = int(math.ceil(duration * rate))
    delay = min(frames, round(track["start"] * rate))
    available = max(0, min(end - begin, frames - delay))
    silence = bytes(4096 * 4)
    with wave.open(str(destination), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        def zeros(count):
            while count:
                chunk = min(count, 4096)
                wav.writeframesraw(silence[:chunk * 4])
                count -= chunk
        zeros(delay)
        if track["muted"]:
            zeros(available)
        else:
            for offset in range(0, available, 4096):
                chunk = audio[:, begin + offset:begin + min(available, offset + 4096)]
                pcm = (np.clip(chunk * track["gain"], -1, 1).T * 32767).astype("<i2")
                wav.writeframesraw(pcm.tobytes())
        zeros(frames - delay - available)
    return destination


def ffmpeg():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


class Encoder:
    def __init__(self, path, width, height, fps, alpha=False, audio=None, offset=0):
        self.path = Path(path)
        self.log = tempfile.TemporaryFile()
        command = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                   "-pixel_format", "rgba", "-video_size", f"{width}x{height}", "-framerate", str(fps), "-i", "pipe:0"]
        if audio:
            command += ["-ss", str(offset), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0?",
                        "-af", "apad", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        command += (["-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p10le", "-alpha_bits", "16"]
                    if alpha else ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
        command += [str(path)]
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.log,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except BaseException:
            self.log.close()
            raise

    def error(self):
        self.log.seek(0)
        return self.log.read().decode("utf-8", errors="replace")[-2500:]

    def write(self, frame):
        try:
            self.process.stdin.write(frame.convert("RGBA").tobytes())
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError("Typography encoder failed: " + self.error()) from exc

    def close(self):
        self.process.stdin.close()
        code = self.process.wait(timeout=180)
        if code:
            raise RuntimeError("Typography export failed: " + self.error())
        self.log.close()

    def abort(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=30)
        try:
            self.process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        self.log.close()


class Footage:
    def __init__(self, path, width, height):
        self.container = av.open(str(path))
        if not self.container.streams.video:
            self.container.close()
            raise ValueError("The selected file has no video stream.")
        self.stream = self.container.streams.video[0]
        self.frames = iter(self.container.decode(self.stream))
        self.next = next(self.frames, None)
        if self.next is None:
            self.container.close()
            raise ValueError("The selected video contains no decodable frames.")
        self.origin = float(self.next.time or 0)
        self.current = self.next
        self.size = (width, height)
        self.last_pts = None
        self.image = None

    def frame(self, seconds):
        while self.next is not None and float(self.next.time or 0) - self.origin <= seconds + 1e-7:
            self.current = self.next
            self.next = next(self.frames, None)
        if self.image is None or self.last_pts != self.current.pts:
            self.image = ImageOps.fit(self.current.to_image(), self.size, Image.Resampling.LANCZOS).convert("RGBA")
            self.last_pts = self.current.pts
        return self.image

    def close(self):
        self.container.close()


def render(project, output, width=1920, height=1080, fps=30, format="Transparent MOV",
           samples=3, video=None, cancelled=None, progress=None, audio=None):
    project = validate_project(project)
    if format not in FORMATS or samples not in (1, 3, 5):
        raise ValueError("Unknown export format or motion-blur sample count.")
    if type(width) is not int or type(height) is not int or min(width, height) < 64 or max(width, height) > 4096 or width % 2 or height % 2:
        raise ValueError("Use even canvas dimensions between 64 and 4096.")
    if type(fps) is not int or not 1 <= fps <= 60:
        raise ValueError("FPS must be between 1 and 60.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Install mariotyport/requirements.txt and run python -m playwright install chromium with ComfyUI's Python.") from exc
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    destination = output / ("typography.mov" if format == "Transparent MOV" else "typography.mp4")
    if format == "PNG sequence":
        destination = output / "frames"
        destination.mkdir()
    preview_path = destination if format == "MP4 composite" else output / "preview.mp4"
    encoders, footage = [], None
    frame_count = math.ceil(project["duration"] * fps)
    poster_number = min(frame_count - 1, round(min(project["duration"] / 2, 1.2) * fps))
    try:
        soundtrack = None
        if project["audio"]["file"]:
            if audio is None:
                raise ValueError("Resolve the project's soundtrack file before rendering.")
            soundtrack = prepare_soundtrack(project["audio"], audio, frame_count / fps, output / "soundtrack.wav")
        if format == "MP4 composite" and video:
            footage = Footage(video, width, height)
        if format != "PNG sequence":
            encoder = Encoder(destination, width, height, fps, format == "Transparent MOV",
                              soundtrack or (video if format == "MP4 composite" else None),
                              0 if soundtrack else project["video_offset"])
            encoders.append(encoder)
        preview = encoder if format == "MP4 composite" else Encoder(preview_path, width, height, fps, audio=soundtrack)
        if format != "MP4 composite":
            encoders.append(preview)
        checker = Image.new("RGBA", (width, height), (38, 39, 42, 255))
        draw = ImageDraw.Draw(checker)
        step = max(8, min(width, height) // 24)
        for y in range(0, height, step):
            for x in range(0, width, step):
                if (x // step + y // step) % 2:
                    draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(51, 52, 55, 255))
        solid = Image.new("RGBA", (width, height), project["background"])
        web = Path(__file__).parent / "web"
        fonts = {name: base64.b64encode((web / "fonts" / f"Tajawal-{name}.ttf").read_bytes()).decode("ascii") for name in FONTS}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 960, "height": 540})
                page.route("**/*", lambda route: route.abort())
                page.set_content('<canvas id="stage"></canvas>')
                page.add_script_tag(path=str(web / "engine.js"))
                page.evaluate("""async ({fonts,width,height,project}) => {
                    await Promise.all(Object.entries(fonts).map(async ([name,data]) => {
                        const face=new FontFace('MT-'+name,'url(data:font/ttf;base64,'+data+')');
                        document.fonts.add(await face.load());
                    }));
                    window.stage=document.getElementById('stage'); stage.width=width; stage.height=height;
                    window.renderer=MarioType.createRenderer(stage); window.project=project;
                }""", {"fonts": fonts, "width": width, "height": height, "project": project})
                for number in range(frame_count):
                    if cancelled and cancelled.is_set():
                        raise InterruptedError("Typography render cancelled.")
                    data = page.evaluate("""({time,fps,samples}) => {
                        renderer.render(project,time,{fps,samples}); return stage.toDataURL('image/png').split(',')[1];
                    }""", {"time": number / fps, "fps": fps, "samples": samples})
                    with Image.open(io.BytesIO(base64.b64decode(data))) as png:
                        frame = png.convert("RGBA")
                    if number == poster_number:
                        frame.save(output / "alpha.png")
                    if format == "MP4 composite":
                        background = footage.frame(number / fps + project["video_offset"]) if footage else solid
                        result = Image.alpha_composite(background, frame)
                        encoder.write(result)
                    else:
                        if format == "PNG sequence":
                            frame.save(destination / f"{number:06d}.png")
                        else:
                            encoder.write(frame)
                        result = Image.alpha_composite(checker, frame)
                        preview.write(result)
                    if number == poster_number:
                        result.convert("RGB").save(output / "poster.jpg", quality=95)
                    if progress:
                        progress(number + 1, frame_count)
            finally:
                browser.close()
        for encoder in encoders:
            encoder.close()
        manifest = dict(project=project, width=width, height=height, fps=fps, samples=samples, format=format,
                        frame_count=frame_count, video=str(video) if video else "", export_path=str(destination))
        (output / "project.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return dict(path=str(destination), preview=str(preview_path), poster=str(output / "poster.jpg"),
                    alpha=str(output / "alpha.png"), frames=frame_count)
    except BaseException:
        # Close every encoder before removing files: Windows locks active media inputs/outputs.
        for encoder in encoders:
            encoder.abort()
        if footage:
            footage.close()
            footage = None
        # This directory was created exclusively for this render above.
        shutil.rmtree(output)
        raise
    finally:
        if footage:
            footage.close()
