"""
Auto-selects the best available image generation provider
based on installed packages and available API keys.
"""

MODELS = {
    "fal":            {"requires_key": "fal",        "quality": 5, "speed": 5, "cost": "free_tier"},
    "hf_inference":   {"requires_key": None,          "quality": 3, "speed": 3, "cost": "free"},
    "replicate":      {"requires_key": "replicate",   "quality": 5, "speed": 4, "cost": "paid"},
    "openai":         {"requires_key": "openai",      "quality": 5, "speed": 4, "cost": "paid"},
    "diffusers_local":{"requires_key": None,          "quality": 4, "speed": 1, "cost": "free"},
}

def get_best_model(model: str, api_keys: dict) -> str:
    if model != "auto":
        return model

    # Priority: fal free > HF > diffusers local (no GPU needed, CPU fallback)
    if api_keys.get("fal"):
        return "fal"
    if api_keys.get("openai"):
        return "openai"
    if api_keys.get("replicate"):
        return "replicate"
    # HF works without a key (rate-limited) or with free key
    return "hf_inference"
