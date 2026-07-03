#!/bin/bash
set -e

echo ""
echo "  Luna1.1 — AI Creative Studio"
echo "  Installing..."
echo ""

# Check Python
python3 --version || { echo "Python 3.8+ required"; exit 1; }

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Core install
pip install --upgrade pip
pip install requests python-dotenv edge-tts

# ffmpeg check
if ! command -v ffmpeg &> /dev/null; then
    echo ""
    echo "  ffmpeg not found. Install it:"
    echo "    Ubuntu/Debian: sudo apt install ffmpeg"
    echo "    Mac:           brew install ffmpeg"
    echo "    Windows:       https://ffmpeg.org/download.html"
    echo ""
fi

# Copy .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env — add your API keys there (all optional)"
fi

# Create output dirs
mkdir -p output/{images,videos,audio,final}

echo ""
echo "  Done! Run: source .venv/bin/activate"
echo ""
echo "  Quick start:"
echo "    python main.py image  \"a futuristic city at sunset\""
echo "    python main.py tts    \"Hello from Luna1.1\""
echo "    python main.py studio \"a short film about a lonely robot\" --style cinematic"
echo ""
