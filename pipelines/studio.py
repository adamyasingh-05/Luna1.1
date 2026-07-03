"""
Studio pipeline — the flagship feature.
Takes a single creative brief and orchestrates image, video, TTS, music, and editing
into a finished production. This is where Luna1.1 beats OpenMontage:
smarter scene planning, better prompt engineering, cleaner orchestration.
"""

import shutil
import time
from pathlib import Path
from argparse import Namespace
from utils.logger import log
from utils.prompt_enhancer import enhance_studio_prompt
from pipelines.image import ImagePipeline
from pipelines.video import VideoPipeline
from pipelines.tts import TTSPipeline
from pipelines.music import MusicPipeline
from pipelines.editor import EditorPipeline, run_ffmpeg


def _require_ffmpeg():
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is required for the studio pipeline but was not found.\n\n"
            "  macOS:   brew install ffmpeg\n"
            "  Ubuntu:  sudo apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html  (add to PATH after installing)\n\n"
            "After installing, re-run: python main.py doctor"
        )


class StudioPipeline:
    def __init__(self, config):
        self.config = config
        self.out_dir = Path(config["output_dir"]) / "final"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self, args):
        # Check hard dependencies before spending time on generation
        _require_ffmpeg()

        prompt      = args.prompt
        style       = getattr(args, "style",    "cinematic")
        duration    = int(getattr(args, "duration", 30))
        voice       = getattr(args, "voice",    "auto")
        do_music    = getattr(args, "music",    False)
        captions    = getattr(args, "captions", False)
        output      = getattr(args, "output",   "")

        project_name = output or f"project_{int(time.time())}"
        project_dir  = self.out_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        log(f"Starting studio production: {prompt[:60]}", "section")
        log(f"Style: {style} | Duration: {duration}s | Project: {project_name}", "step")

        # Phase 1: Plan
        log("Phase 1: Planning scenes...", "section")
        plan = enhance_studio_prompt(prompt, style)
        log(f"Title: {plan['title']}", "info")
        log(f"Scenes: {len(plan['scenes'])}", "info")
        self._save_plan(plan, project_dir)

        # Phase 2: Generate visuals per scene
        log("Phase 2: Generating scene visuals...", "section")
        scene_videos  = []
        img_pipe = ImagePipeline(self.config)
        vid_pipe = VideoPipeline(self.config)

        for scene in plan["scenes"]:
            i = scene["index"]
            log(f"  Scene {i}: {scene['original'][:50]}", "step")

            img_args = Namespace(
                prompt=scene["image_prompt"],
                style=style, model="auto",
                size="1024x576", count=1, enhance=False,
                output=str(project_dir / f"scene_{i}.png")
            )
            img_results = img_pipe.run(img_args)
            img_path = img_results[0] if img_results else None

            vid_args = Namespace(
                prompt=scene["video_prompt"],
                style=style, model="auto",
                duration=str(max(1, duration // len(plan["scenes"]))),
                fps="24", enhance=False,
                output=str(project_dir / f"scene_{i}.mp4")
            )
            try:
                vid_path = vid_pipe.run(vid_args)
                scene_videos.append(str(vid_path))
            except Exception as e:
                log(f"  Video gen failed for scene {i}: {e}", "warn")
                if img_path:
                    log("  Falling back to image-to-video via ffmpeg.", "warn")
                    vid_path = project_dir / f"scene_{i}.mp4"
                    self._image_to_video(
                        str(img_path), str(vid_path),
                        max(1, duration // len(plan["scenes"]))
                    )
                    scene_videos.append(str(vid_path))
                else:
                    log(f"  Skipping scene {i} — no image or video available.", "warn")

        if not scene_videos:
            raise RuntimeError(
                "No scenes were generated successfully.\n"
                "Check your API keys (run 'python main.py doctor') and try again."
            )

        # Phase 3: Voiceover
        log("Phase 3: Generating voiceover...", "section")
        narration = self._build_narration(plan)
        if voice == "auto":
            voice = "en-US-GuyNeural" if style == "documentary" else "en-US-JennyNeural"

        tts_args = Namespace(
            text=narration, voice=voice,
            speed="+0%", output=str(project_dir / "narration.mp3"),
            list_voices=False
        )
        voice_path = TTSPipeline(self.config).run(tts_args)

        # Phase 4: Background music (optional, fail gracefully)
        music_path = None
        if do_music:
            log("Phase 4: Generating background music...", "section")
            music_prompt = self._music_prompt(style)
            mus_args = Namespace(
                prompt=music_prompt,
                duration=str(duration),
                output=str(project_dir / "music.wav")
            )
            try:
                music_path = MusicPipeline(self.config).run(mus_args)
            except Exception as e:
                log(
                    f"Music generation failed: {e}\n"
                    "  Continuing without background music.\n"
                    "  Tip: Set HF_API_KEY in .env for better music generation reliability.",
                    "warn"
                )

        # Phase 5: Assemble
        log("Phase 5: Assembling final video...", "section")
        if len(scene_videos) > 1:
            combined = self._concat_videos(scene_videos, project_dir)
        else:
            combined = scene_videos[0]

        edit_args = Namespace(
            video=combined,
            audio=str(voice_path) if voice_path else "",
            music=str(music_path) if music_path else "",
            captions=captions,
            trim="",
            output=str(project_dir / f"{project_name}_final.mp4")
        )
        final = EditorPipeline(self.config).run(edit_args)

        log(f"\nProduction complete!", "info")
        log(f"Final video: {final}", "info")
        log(f"Project files: {project_dir}", "info")
        return final

    def _concat_videos(self, video_paths, project_dir):
        list_file = project_dir / "concat_list.txt"
        list_file.write_text("\n".join(f"file '{p}'" for p in video_paths))
        out = project_dir / "combined.mp4"
        run_ffmpeg([
            "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(out)
        ], "Concatenating scenes...")
        return str(out)

    def _image_to_video(self, img_path, out_path, duration):
        run_ffmpeg([
            "-loop", "1", "-i", img_path,
            "-c:v", "libx264", "-t", str(duration),
            "-pix_fmt", "yuv420p", "-vf", "scale=1024:576",
            out_path
        ], f"Converting image to {duration}s video clip...")

    def _build_narration(self, plan) -> str:
        lines = [f"{plan['title']}."]
        for scene in plan["scenes"]:
            lines.append(scene["original"])
        return " ".join(lines)

    def _music_prompt(self, style) -> str:
        prompts = {
            "cinematic":     "epic orchestral cinematic score, dramatic strings, powerful",
            "documentary":   "calm ambient background music, subtle, thoughtful",
            "anime":         "upbeat anime opening theme, energetic, J-pop inspired",
            "promo":         "modern upbeat background music, corporate, motivational",
        }
        return prompts.get(style, "ambient background music, calm, atmospheric")

    def _save_plan(self, plan, project_dir):
        import json
        plan_path = project_dir / "production_plan.json"
        plan_path.write_text(json.dumps(plan, indent=2))
        log(f"Production plan saved: {plan_path}", "info")
