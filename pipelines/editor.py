"""
Video editing pipeline — wraps ffmpeg for trimming, mixing audio, adding captions.
Uses Whisper (openai-whisper, free/local) for auto-captions.
"""

import shutil
import subprocess
import time
from pathlib import Path
from utils.logger import log


def _check_ffmpeg():
    """Raise a clear error if ffmpeg is not installed."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is not installed or not in your PATH.\n\n"
            "  macOS:   brew install ffmpeg\n"
            "  Ubuntu:  sudo apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html  (add to PATH after installing)\n\n"
            "After installing, re-run: python main.py doctor"
        )


def run_ffmpeg(args_list, desc=""):
    _check_ffmpeg()
    if desc:
        log(desc, "step")
    result = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error"] + args_list,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed while: {desc or 'running command'}\n"
            f"Details: {result.stderr[:400]}\n"
            "Tip: run 'python main.py doctor' to verify your ffmpeg installation."
        )
    return result


class EditorPipeline:
    def __init__(self, config):
        self.config = config
        self.out_dir = Path(config["output_dir"]) / "final"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self, args):
        video    = getattr(args, "video",    "")
        audio    = getattr(args, "audio",    "")
        music    = getattr(args, "music",    "")
        captions = getattr(args, "captions", False)
        trim     = getattr(args, "trim",     "")
        output   = getattr(args, "output",   "")

        if not video:
            raise ValueError("--video is required for the edit command")

        # Check ffmpeg early so the error is clear
        _check_ffmpeg()

        current = Path(video)
        outfile  = self._output_path(output)

        # Step 1: Trim
        if trim:
            start, end = trim.split("-")
            trimmed = self.out_dir / f"trimmed_{int(time.time())}.mp4"
            run_ffmpeg([
                "-i", str(current),
                "-ss", start, "-to", end,
                "-c", "copy", str(trimmed)
            ], f"Trimming {start}s to {end}s...")
            current = trimmed

        # Step 2: Mix voiceover
        if audio:
            mixed = self.out_dir / f"mixed_voice_{int(time.time())}.mp4"
            run_ffmpeg([
                "-i", str(current), "-i", audio,
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.8[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-shortest",
                str(mixed)
            ], "Mixing voiceover...")
            current = mixed

        # Step 3: Mix background music
        if music:
            music_mixed = self.out_dir / f"mixed_music_{int(time.time())}.mp4"
            run_ffmpeg([
                "-i", str(current), "-i", music,
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.3[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-shortest",
                str(music_mixed)
            ], "Mixing background music (at 30% volume)...")
            current = music_mixed

        # Step 4: Add captions
        if captions:
            current = self._add_captions(current)

        # Final copy to output
        run_ffmpeg(["-i", str(current), "-c", "copy", str(outfile)], "Finalizing...")
        log(f"Final video: {outfile}", "info")
        return outfile

    def _add_captions(self, video_path):
        log("Transcribing with Whisper for captions...", "step")
        try:
            import whisper
        except ImportError:
            log(
                "openai-whisper is not installed — skipping captions.\n"
                "  To enable: pip install openai-whisper",
                "warn"
            )
            return video_path

        model = whisper.load_model("base")
        result = model.transcribe(str(video_path))

        srt_path = self.out_dir / f"captions_{int(time.time())}.srt"
        self._write_srt(result["segments"], srt_path)
        log(f"Captions written: {srt_path}", "info")

        captioned = self.out_dir / f"captioned_{int(time.time())}.mp4"
        run_ffmpeg([
            "-i", str(video_path),
            "-vf", (
                f"subtitles={srt_path}:"
                "force_style='FontSize=20,PrimaryColour=&HFFFFFF,"
                "OutlineColour=&H000000,Outline=2'"
            ),
            str(captioned)
        ], "Burning captions into video...")
        return captioned

    def _write_srt(self, segments, path):
        lines = []
        for i, seg in enumerate(segments, 1):
            start = self._fmt_time(seg["start"])
            end   = self._fmt_time(seg["end"])
            lines.append(f"{i}\n{start} --> {end}\n{seg['text'].strip()}\n")
        path.write_text("\n".join(lines), encoding="utf-8")

    def _fmt_time(self, seconds):
        h  = int(seconds // 3600)
        m  = int((seconds % 3600) // 60)
        s  = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def _output_path(self, output):
        if output:
            p = Path(output)
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        return self.out_dir / f"edit_{int(time.time())}.mp4"
