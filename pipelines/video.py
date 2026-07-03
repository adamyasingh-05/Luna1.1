"""
Video generation pipeline.
Strategy: tries best available free provider first, falls back gracefully.
Free options: fal.ai free tier (Wan, LTX), HuggingFace Inference.
Paid options: Replicate, fal.ai paid.

Important limitations:
  - fal.ai free tier has rate limits; heavy use will return 429 errors.
  - HuggingFace video endpoint is experimental and often slow or unavailable.
  - All API-based video generation is network-dependent; if providers are down, generation fails.
  - The ffmpeg image-to-video fallback always works (requires ffmpeg installed).
"""

import time
from pathlib import Path
from utils.logger import log
from utils.prompt_enhancer import enhance_video_prompt


PROVIDER_PRIORITY = ["fal_free", "hf_inference", "replicate", "fal_paid"]

MODEL_MAP = {
    "auto":  "fal_free",
    "wan":   "fal_free",
    "ltx":   "fal_free",
    "kling": "fal_paid",
    "veo":   "fal_paid",
}


class VideoPipeline:
    def __init__(self, config):
        self.config = config
        self.out_dir = Path(config["output_dir"]) / "videos"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self, args):
        prompt   = args.prompt
        style    = getattr(args, "style",    "cinematic")
        model    = getattr(args, "model",    "auto")
        duration = getattr(args, "duration", "5")
        enhance  = getattr(args, "enhance",  True)
        output   = getattr(args, "output",   "")

        log(f"Prompt: {prompt}", "step")

        if enhance:
            enhanced = enhance_video_prompt(prompt, style, duration)
            log(f"Enhanced: {enhanced['prompt'][:80]}...", "step")
        else:
            enhanced = {"prompt": prompt, "negative": ""}

        provider = MODEL_MAP.get(model, "fal_free")
        log(f"Using provider: {provider} | duration: {duration}s", "step")

        outfile = self._output_path(output)
        path = self._generate(provider, enhanced, duration, outfile)
        if path:
            log(f"Video saved: {path}", "info")
        return path

    def _generate(self, provider, enhanced, duration, outfile):
        if provider in ("fal_free", "fal_paid"):
            return self._fal(enhanced, duration, outfile, paid=(provider == "fal_paid"))
        elif provider == "replicate":
            return self._replicate(enhanced, duration, outfile)
        elif provider == "hf_inference":
            return self._hf_inference(enhanced, outfile)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _fal(self, enhanced, duration, outfile, paid=False):
        try:
            import fal_client
        except ImportError:
            raise RuntimeError(
                "fal-client is not installed. Run: pip install fal-client\n"
                "Then set FAL_API_KEY in .env (get a free key at fal.ai)."
            )
        model_id = (
            "fal-ai/wan/t2v-1.3b" if not paid
            else "fal-ai/kling-video/v1.6/standard/text-to-video"
        )
        log(f"Calling fal.ai model: {model_id} (may take 30–120s)...", "step")
        if not paid:
            log(
                "Note: fal.ai free tier has rate limits. If you get 429 errors,\n"
                "  wait a few minutes or add billing at fal.ai for uninterrupted use.",
                "warn"
            )
        try:
            result = fal_client.run(
                model_id,
                arguments={
                    "prompt": enhanced["prompt"],
                    "negative_prompt": enhanced.get("negative", ""),
                    "num_frames": int(duration) * 8,
                    "fps": 8,
                }
            )
        except Exception as e:
            err = str(e)
            if "429" in err or "rate" in err.lower():
                raise RuntimeError(
                    "fal.ai rate limit reached. Your free-tier quota is exhausted.\n"
                    "  Wait a few minutes and retry, or add billing at fal.ai."
                )
            raise RuntimeError(f"fal.ai error: {e}")

        url = result.get("video", {}).get("url") or result.get("url", "")
        if not url:
            raise RuntimeError(
                f"fal.ai returned no video URL. Response: {result}\n"
                "This may indicate the model changed its output format. "
                "Check https://fal.ai for API updates."
            )
        return self._download_url(url, outfile)

    def _replicate(self, enhanced, duration, outfile):
        try:
            import replicate
        except ImportError:
            raise RuntimeError(
                "replicate is not installed. Run: pip install replicate\n"
                "Then set REPLICATE_API_KEY in .env."
            )
        log("Calling Replicate (LTX-Video)...", "step")
        output = replicate.run(
            "lightricks/ltx-video",
            input={
                "prompt": enhanced["prompt"],
                "negative_prompt": enhanced.get("negative", ""),
                "num_frames": int(duration) * 8,
            }
        )
        return self._download_url(str(output), outfile)

    def _hf_inference(self, enhanced, outfile):
        import requests
        log("Calling HuggingFace text-to-video (experimental, may be slow)...", "step")
        log(
            "HuggingFace video generation is experimental and often times out.\n"
            "  For more reliable video: set FAL_API_KEY in .env.",
            "warn"
        )
        url = "https://api-inference.huggingface.co/models/ali-vilab/text-to-video-ms-1.7b"
        api_key = self.config["api_keys"]["huggingface"]
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            resp = requests.post(url, headers=headers, json={"inputs": enhanced["prompt"]}, timeout=300)
        except requests.exceptions.Timeout:
            raise RuntimeError(
                "HuggingFace video endpoint timed out (>300s).\n"
                "  This endpoint is unreliable. Set FAL_API_KEY in .env for better results."
            )
        if resp.status_code == 503:
            raise RuntimeError("HuggingFace video model loading (503). Try again in 60 seconds.")
        if resp.status_code != 200:
            raise RuntimeError(
                f"HuggingFace error {resp.status_code}: {resp.text[:200]}\n"
                "  Consider setting FAL_API_KEY in .env for reliable video generation."
            )
        outfile.write_bytes(resp.content)
        return outfile

    def _download_url(self, url, outfile):
        import requests
        log("Downloading result...", "step")
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        outfile.write_bytes(resp.content)
        return outfile

    def _output_path(self, output):
        if output:
            p = Path(output)
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        return self.out_dir / f"video_{int(time.time())}.mp4"
