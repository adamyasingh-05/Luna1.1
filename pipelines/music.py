"""
Background music generation pipeline.
Uses MusicGen via HuggingFace Inference API (free) or local transformers.

Important limitations:
  - HuggingFace free endpoint for MusicGen is unreliable and often times out.
    A HF_API_KEY (free account) significantly improves reliability.
  - Local MusicGen requires torch + transformers and is slow on CPU (~2-5 min for 30s clip).
  - There is currently no rock-solid free fallback for music generation.
    If both options fail, the studio pipeline will continue without background music.
"""

import time
from pathlib import Path
from utils.logger import log


class MusicPipeline:
    def __init__(self, config):
        self.config = config
        self.out_dir = Path(config["output_dir"]) / "audio"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self, args):
        prompt   = args.prompt
        duration = int(getattr(args, "duration", 30))
        output   = getattr(args, "output", "")

        log(f"Generating music: {prompt}", "step")
        log(f"Duration: {duration}s", "step")

        outfile  = self._output_path(output)
        api_key  = self.config["api_keys"]["huggingface"]

        if not api_key:
            log(
                "No HF_API_KEY set. MusicGen free endpoint is rate-limited and unreliable without a key.\n"
                "  → Get a free key at huggingface.co/settings/tokens and add HF_API_KEY to .env.",
                "warn"
            )

        # Try HF Inference API first (free)
        try:
            path = self._hf_musicgen(prompt, duration, outfile, api_key)
            log(f"Music saved: {path}", "info")
            return path
        except Exception as e:
            log(f"HuggingFace MusicGen failed: {e}", "warn")
            log("Trying local MusicGen (requires transformers + torch; slow on CPU)...", "warn")

        try:
            path = self._local_musicgen(prompt, duration, outfile)
            log(f"Music saved: {path}", "info")
            return path
        except ImportError:
            raise RuntimeError(
                "Music generation failed.\n"
                "  Option 1 (recommended): Set HF_API_KEY in .env (free at huggingface.co).\n"
                "  Option 2 (local, slow):  pip install transformers torch scipy\n"
                "  The studio pipeline will skip music if you re-run without --music."
            )
        except Exception as e:
            raise RuntimeError(
                f"Local MusicGen also failed: {e}\n"
                "  Try again, or remove --music from your studio command to skip music generation."
            )

    def _hf_musicgen(self, prompt, duration, outfile, api_key):
        import requests
        url = "https://api-inference.huggingface.co/models/facebook/musicgen-small"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": duration * 50},
        }
        log("Calling HuggingFace MusicGen (may take 60–180s)...", "step")
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=200)
        except requests.exceptions.Timeout:
            raise RuntimeError(
                "HuggingFace MusicGen timed out (>200s). "
                "The model server may be overloaded. Try again in a minute, "
                "or add HF_API_KEY in .env for higher priority."
            )
        if resp.status_code == 503:
            raise RuntimeError("HuggingFace MusicGen is loading (503). Try again in 30 seconds.")
        if resp.status_code == 429:
            raise RuntimeError(
                "HuggingFace rate limit (429). "
                "Add HF_API_KEY in .env (free account) to get a higher limit."
            )
        if resp.status_code != 200:
            raise RuntimeError(f"HuggingFace error {resp.status_code}: {resp.text[:200]}")
        outfile.write_bytes(resp.content)
        return outfile

    def _local_musicgen(self, prompt, duration, outfile):
        try:
            from transformers import pipeline
            import scipy
        except ImportError:
            raise ImportError(
                "transformers and/or scipy are not installed.\n"
                "Run: pip install transformers torch scipy"
            )
        log("⚠  Running MusicGen locally on CPU. A 30s clip may take 2–5 minutes — the tool has NOT crashed.", "warn")
        synthesiser = pipeline("text-to-audio", "facebook/musicgen-small")
        music = synthesiser(prompt, forward_params={"max_new_tokens": duration * 50})
        scipy.io.wavfile.write(str(outfile), rate=music["sampling_rate"], data=music["audio"])
        return outfile

    def _output_path(self, output):
        if output:
            p = Path(output)
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        return self.out_dir / f"music_{int(time.time())}.wav"
