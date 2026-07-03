"""
Image generation pipeline.
Supports: HuggingFace Inference API (free), fal.ai (free tier),
          Replicate, OpenAI DALL-E, local SDXL-Turbo (CPU fallback).
Auto-selects best available provider based on installed packages and API keys.
"""

import os
import time
from pathlib import Path
from utils.logger import log
from utils.prompt_enhancer import enhance_image_prompt
from models.image_models import get_best_model, MODELS


class ImagePipeline:
    def __init__(self, config):
        self.config = config
        self.out_dir = Path(config["output_dir"]) / "images"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self, args):
        prompt  = args.prompt
        style   = getattr(args, "style",   "")
        model   = getattr(args, "model",   "auto")
        size    = getattr(args, "size",    "1024x1024")
        count   = getattr(args, "count",   1)
        enhance = getattr(args, "enhance", self.config["image"]["enhance_prompts"])
        output  = getattr(args, "output",  "")

        log(f"Prompt: {prompt}", "step")

        if enhance:
            enhanced = enhance_image_prompt(prompt, style)
            log(f"Enhanced: {enhanced['prompt'][:80]}...", "step")
        else:
            enhanced = {"prompt": prompt, "negative": "", "original": prompt}

        provider = get_best_model(model, self.config["api_keys"])
        log(f"Using provider: {provider}", "step")

        results = []
        for i in range(count):
            log(f"Generating image {i+1}/{count}...", "section")
            outfile = self._output_path(output, i, count)
            path = self._generate(provider, enhanced, size, outfile)
            if path:
                results.append(path)
                log(f"Saved: {path}", "info")

        log(f"Done! {len(results)} image(s) saved to {self.out_dir}", "info")
        return results

    def _generate(self, provider, enhanced, size, outfile):
        if provider == "hf_inference":
            return self._hf_inference(enhanced, outfile)
        elif provider == "fal":
            return self._fal(enhanced, size, outfile)
        elif provider == "replicate":
            return self._replicate(enhanced, size, outfile)
        elif provider == "openai":
            return self._openai(enhanced, size, outfile)
        elif provider == "diffusers_local":
            return self._diffusers_local(enhanced, size, outfile)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _hf_inference(self, enhanced, outfile):
        """HuggingFace Inference API — free, no local GPU needed.
        Note: The free endpoint can be slow or temporarily unavailable.
        If it keeps failing, set HF_API_KEY in .env (free account) for better reliability,
        or switch to fal.ai (FAL_API_KEY).
        """
        import requests
        api_key = self.config["api_keys"]["huggingface"]
        model_id = "stabilityai/stable-diffusion-xl-base-1.0"
        url = f"https://api-inference.huggingface.co/models/{model_id}"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        payload = {
            "inputs": enhanced["prompt"],
            "parameters": {
                "negative_prompt": enhanced.get("negative", ""),
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
            }
        }
        log("Calling HuggingFace Inference API (this can take 30–120s on cold start)...", "step")
        if not api_key:
            log("Tip: Set HF_API_KEY in .env for a more reliable free tier.", "warn")
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
        except requests.exceptions.Timeout:
            raise RuntimeError(
                "HuggingFace API timed out (>120s). The model may be loading — try again in 30s, "
                "or add HF_API_KEY / FAL_API_KEY in .env for better reliability."
            )
        if resp.status_code == 503:
            raise RuntimeError(
                "HuggingFace model is loading (503). Wait 20–30 seconds and retry. "
                "For faster results set HF_API_KEY or FAL_API_KEY in .env."
            )
        if resp.status_code == 429:
            raise RuntimeError(
                "HuggingFace rate limit hit (429). "
                "Add HF_API_KEY in .env (free account) to get a higher rate limit."
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"HuggingFace API error {resp.status_code}: {resp.text[:200]}\n"
                "Tip: run 'python main.py doctor' to check your setup."
            )
        outfile.write_bytes(resp.content)
        return outfile

    def _fal(self, enhanced, size, outfile):
        """fal.ai — free tier available, fast FLUX generation.
        Note: fal.ai free tier has rate limits. If you hit them you'll get a 429 error.
        Consider upgrading to a paid plan or adding billing at fal.ai for uninterrupted use.
        """
        try:
            import fal_client
        except ImportError:
            raise RuntimeError(
                "fal-client is not installed. Run: pip install fal-client\n"
                "Then set FAL_API_KEY in .env (get a free key at fal.ai)."
            )
        w, h = size.split("x")
        try:
            result = fal_client.run(
                "fal-ai/flux/schnell",
                arguments={
                    "prompt": enhanced["prompt"],
                    "image_size": {"width": int(w), "height": int(h)},
                    "num_inference_steps": 4,
                    "num_images": 1,
                }
            )
        except Exception as e:
            err = str(e)
            if "429" in err or "rate" in err.lower():
                raise RuntimeError(
                    "fal.ai rate limit reached. Your free-tier quota is exhausted for now.\n"
                    "Options: wait a few minutes and retry, or add billing at fal.ai."
                )
            raise RuntimeError(f"fal.ai error: {e}")
        url = result["images"][0]["url"]
        return self._download_url(url, outfile)

    def _replicate(self, enhanced, size, outfile):
        """Replicate — pay per use, very high quality."""
        try:
            import replicate
        except ImportError:
            raise RuntimeError(
                "replicate is not installed. Run: pip install replicate\n"
                "Then set REPLICATE_API_KEY in .env."
            )
        w, h = size.split("x")
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={"prompt": enhanced["prompt"], "width": int(w), "height": int(h)}
        )
        return self._download_url(output[0], outfile)

    def _openai(self, enhanced, size, outfile):
        """OpenAI DALL-E 3."""
        try:
            import openai
        except ImportError:
            raise RuntimeError(
                "openai is not installed. Run: pip install openai\n"
                "Then set OPENAI_API_KEY in .env."
            )
        client = openai.OpenAI()
        resp = client.images.generate(
            model="dall-e-3",
            prompt=enhanced["prompt"],
            size=size,
            quality="hd",
            n=1,
        )
        return self._download_url(resp.data[0].url, outfile)

    def _diffusers_local(self, enhanced, size, outfile):
        """Fully local via diffusers — requires torch + diffusers installed.
        WARNING: On CPU this takes 5–15 minutes per image. This is normal — the model
        is running without a GPU. If generation seems stuck, it hasn't crashed; just wait.
        For faster results, use fal.ai or HuggingFace API instead.
        """
        try:
            from diffusers import StableDiffusionXLPipeline
            import torch
        except ImportError:
            raise RuntimeError(
                "diffusers and/or torch are not installed.\n"
                "Run: pip install torch diffusers transformers accelerate Pillow\n"
                "Note: local generation on CPU takes 5–15 minutes per image.\n"
                "For faster results, set FAL_API_KEY or HF_API_KEY in .env instead."
            )
        log("⚠  Running local SDXL-Turbo on CPU. This will take 5–15 minutes — the tool has NOT crashed.", "warn")
        log("   First run also downloads ~2 GB of model weights.", "warn")
        log("   For faster generation, set FAL_API_KEY or HF_API_KEY in .env.", "warn")
        w, h = [int(x) for x in size.split("x")]
        pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/sdxl-turbo",
            torch_dtype=torch.float32,
        )
        image = pipe(
            prompt=enhanced["prompt"],
            negative_prompt=enhanced.get("negative", ""),
            width=w, height=h,
            num_inference_steps=4,
            guidance_scale=0.0,
        ).images[0]
        image.save(outfile)
        return outfile

    def _download_url(self, url, outfile):
        import requests
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        outfile.write_bytes(resp.content)
        return outfile

    def _output_path(self, output, i, count):
        if output and count == 1:
            p = Path(output)
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        ts = int(time.time())
        suffix = f"_{i+1}" if count > 1 else ""
        return self.out_dir / f"image_{ts}{suffix}.png"
