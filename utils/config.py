import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONFIG = {
    "output_dir": "output",
    "image": {
        "default_model": "auto",
        "default_size": "1024x1024",
        "enhance_prompts": True,
    },
    "video": {
        "default_model": "auto",
        "default_duration": 5,
        "default_fps": 24,
    },
    "tts": {
        "default_voice": "en-US-JennyNeural",
        "default_speed": "+0%",
    },
    "music": {
        "default_duration": 30,
    },
    "api_keys": {
        "fal":        os.getenv("FAL_API_KEY", ""),
        "huggingface": os.getenv("HF_API_KEY", ""),
        "openai":     os.getenv("OPENAI_API_KEY", ""),
        "replicate":  os.getenv("REPLICATE_API_KEY", ""),
        "muapi":      os.getenv("MUAPI_API_KEY", ""),
    }
}

def load_config():
    cfg_path = Path("config/settings.json")
    if cfg_path.exists():
        with open(cfg_path) as f:
            user_cfg = json.load(f)
        # Merge user config on top of defaults
        merged = DEFAULT_CONFIG.copy()
        for k, v in user_cfg.items():
            if isinstance(v, dict) and k in merged:
                merged[k].update(v)
            else:
                merged[k] = v
        return merged
    return DEFAULT_CONFIG

def save_config(cfg):
    cfg_path = Path("config/settings.json")
    cfg_path.parent.mkdir(exist_ok=True)
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)
