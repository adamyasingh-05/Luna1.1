#!/usr/bin/env python3
"""
Luna1.1 — AI Creative Studio CLI
Run: python main.py --help
"""

import argparse
import sys
from utils.logger import log, banner
from utils.config import load_config
from pipelines.image import ImagePipeline
from pipelines.video import VideoPipeline
from pipelines.tts import TTSPipeline
from pipelines.music import MusicPipeline
from pipelines.editor import EditorPipeline
from pipelines.studio import StudioPipeline


def run_doctor(config):
    """Check all dependencies and API keys, print a health report."""
    import shutil

    log("Running Luna1.1 health check...", "section")
    issues = []
    ok = []

    # ── Required Python packages ──────────────────────────────────────────────
    log("Checking required Python packages...", "step")
    required = {"requests": "requests", "dotenv": "python-dotenv", "edge_tts": "edge-tts"}
    for mod, pkg in required.items():
        try:
            __import__(mod)
            ok.append(f"  ✓ {pkg}")
        except ImportError:
            issues.append(f"  ✗ {pkg} missing — run: pip install {pkg}")

    # ── Optional packages ─────────────────────────────────────────────────────
    log("Checking optional Python packages...", "step")
    optional = {
        "fal_client":  ("fal-client",  "fal.ai image/video generation"),
        "replicate":   ("replicate",   "Replicate models"),
        "openai":      ("openai",      "DALL-E 3 / GPT prompt enhancement / OpenAI TTS"),
        "diffusers":   ("diffusers",   "Local SDXL-Turbo image generation (slow on CPU)"),
        "whisper":     ("openai-whisper", "Auto-captions"),
        "scipy":       ("scipy",       "Local MusicGen"),
        "transformers":("transformers","Local MusicGen / local models"),
    }
    for mod, (pkg, desc) in optional.items():
        try:
            __import__(mod)
            ok.append(f"  ✓ {pkg}  ({desc})")
        except ImportError:
            ok.append(f"  ○ {pkg} not installed  ({desc})  [optional]")

    # ── System binaries ───────────────────────────────────────────────────────
    log("Checking system binaries...", "step")
    bins = {
        "ffmpeg": (
            "Required for video editing, mixing audio, adding captions, and the studio pipeline.\n"
            "    Install: https://ffmpeg.org/download.html  |  brew install ffmpeg  |  apt install ffmpeg"
        )
    }
    for binary, hint in bins.items():
        if shutil.which(binary):
            ok.append(f"  ✓ {binary}")
        else:
            issues.append(f"  ✗ {binary} not found — {hint}")

    # ── API keys ──────────────────────────────────────────────────────────────
    log("Checking API keys...", "step")
    keys = config["api_keys"]
    key_info = {
        "fal":        ("FAL_API_KEY",        "fal.ai — fast image + video (free tier)"),
        "huggingface":("HF_API_KEY",         "HuggingFace — free image + music generation"),
        "openai":     ("OPENAI_API_KEY",     "OpenAI — DALL-E 3, TTS, prompt enhancement"),
        "replicate":  ("REPLICATE_API_KEY",  "Replicate — high-quality models (paid)"),
    }
    any_key = False
    for key_name, (env_var, desc) in key_info.items():
        if keys.get(key_name):
            ok.append(f"  ✓ {env_var} set  ({desc})")
            any_key = True
        else:
            ok.append(f"  ○ {env_var} not set  ({desc})")
    if not any_key:
        ok.append("  ℹ  No API keys set — HuggingFace free tier + EdgeTTS will be used (may be slow/unreliable).")

    # ── Print results ─────────────────────────────────────────────────────────
    print()
    for msg in ok:
        print(msg)

    if issues:
        print()
        log("Issues found:", "warn")
        for msg in issues:
            print(msg)
        print()
        log("Fix the issues above and re-run: python main.py doctor", "warn")
        sys.exit(1)
    else:
        print()
        log("All checks passed. Luna1.1 is ready to use!", "info")


def main():
    banner()
    config = load_config()

    parser = argparse.ArgumentParser(
        prog="luna11",
        description="Luna1.1 — AI Creative Studio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py doctor
  python main.py image  "a futuristic city at sunset, cyberpunk style"
  python main.py video  "a wolf running through a snowy forest"
  python main.py tts    "Hello world" --voice en-US-JennyNeural
  python main.py music  "calm lo-fi hip hop beat"
  python main.py studio "a short film about a lonely robot" --style cinematic
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    subparsers.add_parser("doctor", help="Check all dependencies and API keys")

    # image
    p_img = subparsers.add_parser("image", help="Generate image from text")
    p_img.add_argument("prompt")
    p_img.add_argument("--model",   default="auto")
    p_img.add_argument("--style",   default="")
    p_img.add_argument("--size",    default="1024x1024")
    p_img.add_argument("--count",   type=int, default=1)
    p_img.add_argument("--enhance", action="store_true")
    p_img.add_argument("--output",  default="")

    # video
    p_vid = subparsers.add_parser("video", help="Generate video from text")
    p_vid.add_argument("prompt")
    p_vid.add_argument("--model",    default="auto")
    p_vid.add_argument("--style",    default="")
    p_vid.add_argument("--duration", default="5")
    p_vid.add_argument("--fps",      default="24")
    p_vid.add_argument("--enhance",  action="store_true")
    p_vid.add_argument("--output",   default="")

    # tts
    p_tts = subparsers.add_parser("tts", help="Text-to-speech voiceover")
    p_tts.add_argument("text")
    p_tts.add_argument("--voice",       default="en-US-JennyNeural")
    p_tts.add_argument("--speed",       default="+0%")
    p_tts.add_argument("--output",      default="")
    p_tts.add_argument("--list-voices", action="store_true")

    # music
    p_mus = subparsers.add_parser("music", help="Generate background music")
    p_mus.add_argument("prompt")
    p_mus.add_argument("--duration", default="30")
    p_mus.add_argument("--output",   default="")

    # edit
    p_ed = subparsers.add_parser("edit", help="Edit / assemble video")
    p_ed.add_argument("--video",    default="")
    p_ed.add_argument("--audio",    default="")
    p_ed.add_argument("--music",    default="")
    p_ed.add_argument("--captions", action="store_true")
    p_ed.add_argument("--trim",     default="")
    p_ed.add_argument("--output",   default="")

    # studio
    p_st = subparsers.add_parser("studio", help="Full production pipeline from one prompt")
    p_st.add_argument("prompt")
    p_st.add_argument("--style",    default="cinematic")
    p_st.add_argument("--duration", default="30")
    p_st.add_argument("--voice",    default="auto")
    p_st.add_argument("--music",    action="store_true")
    p_st.add_argument("--captions", action="store_true")
    p_st.add_argument("--output",   default="")

    args = parser.parse_args()

    try:
        if args.command == "doctor":
            run_doctor(config)
        elif args.command == "image":
            ImagePipeline(config).run(args)
        elif args.command == "video":
            VideoPipeline(config).run(args)
        elif args.command == "tts":
            TTSPipeline(config).run(args)
        elif args.command == "music":
            MusicPipeline(config).run(args)
        elif args.command == "edit":
            EditorPipeline(config).run(args)
        elif args.command == "studio":
            StudioPipeline(config).run(args)
    except KeyboardInterrupt:
        log("\nCancelled.", "warn")
        sys.exit(0)
    except Exception as e:
        log(f"Error: {e}", "error")
        sys.exit(1)


if __name__ == "__main__":
    main()
