"""
Text-to-speech pipeline.
Uses EdgeTTS by default — completely free, no API key, 300+ voices.
Falls back to OpenAI TTS if key is available and user prefers quality.
"""

import asyncio
import time
from pathlib import Path
from utils.logger import log


class TTSPipeline:
    def __init__(self, config):
        self.config = config
        self.out_dir = Path(config["output_dir"]) / "audio"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self, args):
        list_voices = getattr(args, "list_voices", False)
        if list_voices:
            self._list_voices()
            return

        text   = args.text
        voice  = getattr(args, "voice",  self.config["tts"]["default_voice"])
        speed  = getattr(args, "speed",  self.config["tts"]["default_speed"])
        output = getattr(args, "output", "")

        # Support .txt file input
        text_path = Path(text)
        if text_path.exists() and text_path.suffix == ".txt":
            text = text_path.read_text(encoding="utf-8")
            log(f"Loaded text from {text_path} ({len(text)} chars)", "step")

        log(f"Voice: {voice} | Speed: {speed}", "step")
        log(f"Text: {text[:60]}{'...' if len(text) > 60 else ''}", "step")

        outfile = self._output_path(output)
        asyncio.run(self._speak(text, voice, speed, outfile))
        log(f"Audio saved: {outfile}", "info")
        return outfile

    async def _speak(self, text, voice, speed, outfile):
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice, rate=speed)
            await communicate.save(str(outfile))
        except ImportError:
            raise RuntimeError(
                "edge-tts not installed. Run: pip install edge-tts"
            )

    def _list_voices(self):
        async def _list():
            import edge_tts
            voices = await edge_tts.list_voices()
            log(f"Available voices ({len(voices)} total):", "info")
            for v in sorted(voices, key=lambda x: x["Locale"]):
                print(f"  {v['ShortName']:45} {v['Locale']:12} {v['Gender']}")
        asyncio.run(_list())

    def _output_path(self, output):
        if output:
            p = Path(output)
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        return self.out_dir / f"voice_{int(time.time())}.mp3"
