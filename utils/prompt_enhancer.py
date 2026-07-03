"""
Smart prompt enhancement — the key differentiator over OpenMontage.
Rewrites basic prompts into high-quality generation-ready prompts.
Works locally (rule-based) or with an LLM if API key is available.
"""

import os
import re

# Style modifier libraries
STYLE_SUFFIXES = {
    "cinematic": (
        "cinematic lighting, anamorphic lens, shallow depth of field, "
        "35mm film, color graded, dramatic atmosphere, professional cinematography"
    ),
    "anime": (
        "anime style, Studio Ghibli inspired, detailed linework, "
        "vibrant colors, cel shading, dramatic sky, Japanese animation"
    ),
    "photorealistic": (
        "photorealistic, 8K resolution, hyperdetailed, DSLR photo, "
        "natural lighting, sharp focus, Canon EOS R5"
    ),
    "artistic": (
        "digital art, concept art, detailed illustration, "
        "ArtStation quality, intricate details, professional artwork"
    ),
    "documentary": (
        "documentary style, handheld camera, natural lighting, "
        "authentic, realistic, journalistic photography"
    ),
    "promo": (
        "commercial photography, studio lighting, clean background, "
        "product quality, high contrast, marketing visual"
    ),
}

NEGATIVE_PROMPTS = {
    "image": (
        "blurry, low quality, distorted, deformed, ugly, bad anatomy, "
        "watermark, text, signature, out of frame, cropped, duplicate"
    ),
    "video": (
        "static, low quality, blurry, jittery, flickering, watermark, "
        "distorted faces, bad motion, inconsistent lighting"
    ),
}

# Quality boosters to prepend for image prompts
IMAGE_QUALITY_PREFIX = "masterpiece, best quality, highly detailed, "


def enhance_image_prompt(prompt: str, style: str = "", use_llm: bool = False) -> dict:
    """Returns enhanced prompt + negative prompt for image generation."""
    if use_llm and os.getenv("OPENAI_API_KEY"):
        return _llm_enhance_image(prompt, style)
    return _rule_enhance_image(prompt, style)


def enhance_video_prompt(prompt: str, style: str = "", duration: str = "5") -> dict:
    """Returns enhanced prompt for video generation."""
    enhanced = prompt.strip()

    # Add motion language if missing
    motion_words = ["moving", "running", "flowing", "walking", "flying", "drifting", "rotating"]
    if not any(w in enhanced.lower() for w in motion_words):
        enhanced = f"Smooth cinematic shot of {enhanced}"

    # Add style
    if style and style in STYLE_SUFFIXES:
        enhanced += f", {STYLE_SUFFIXES[style]}"

    # Add camera motion
    enhanced += ", smooth camera movement, professional cinematography"

    return {
        "prompt": enhanced,
        "negative": NEGATIVE_PROMPTS["video"],
        "original": prompt,
    }


def enhance_studio_prompt(prompt: str, style: str = "cinematic") -> dict:
    """Break a creative brief into scene-level prompts."""
    scenes = _split_into_scenes(prompt)
    enhanced_scenes = []
    for i, scene in enumerate(scenes):
        img = enhance_image_prompt(scene, style)
        vid = enhance_video_prompt(scene, style)
        enhanced_scenes.append({
            "index": i + 1,
            "original": scene,
            "image_prompt": img["prompt"],
            "video_prompt": vid["prompt"],
            "negative": img["negative"],
        })
    return {
        "title": _extract_title(prompt),
        "style": style,
        "scenes": enhanced_scenes,
    }


def _rule_enhance_image(prompt: str, style: str) -> dict:
    enhanced = IMAGE_QUALITY_PREFIX + prompt.strip()
    if style and style in STYLE_SUFFIXES:
        enhanced += f", {STYLE_SUFFIXES[style]}"
    # Boost lighting if not mentioned
    if not any(w in enhanced.lower() for w in ["light", "lit", "lighting", "shadow", "glow"]):
        enhanced += ", perfect lighting"
    return {
        "prompt": enhanced,
        "negative": NEGATIVE_PROMPTS["image"],
        "original": prompt,
    }


def _llm_enhance_image(prompt: str, style: str) -> dict:
    """Use OpenAI to enhance prompt (only if key available)."""
    try:
        import openai
        client = openai.OpenAI()
        style_hint = f" in {style} style" if style else ""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": (
                    "You are an expert prompt engineer for AI image generation. "
                    "Rewrite the user's prompt to be highly detailed, evocative, and optimized "
                    "for best image quality. Return ONLY the enhanced prompt, no explanation."
                )
            }, {
                "role": "user",
                "content": f"Enhance this prompt{style_hint}: {prompt}"
            }],
            max_tokens=200,
        )
        enhanced = resp.choices[0].message.content.strip()
        return {
            "prompt": enhanced,
            "negative": NEGATIVE_PROMPTS["image"],
            "original": prompt,
        }
    except Exception:
        return _rule_enhance_image(prompt, style)


def _split_into_scenes(prompt: str) -> list:
    """Naively split a creative brief into individual scene prompts."""
    # Split on sentence boundaries or numbered lists
    sentences = re.split(r'(?<=[.!?])\s+|(?:\d+\.\s*)', prompt)
    scenes = [s.strip() for s in sentences if len(s.strip()) > 10]
    # Cap at 5 scenes for reasonable run time
    return scenes[:5] if scenes else [prompt]


def _extract_title(prompt: str) -> str:
    words = prompt.strip().split()[:6]
    return " ".join(words).title()
