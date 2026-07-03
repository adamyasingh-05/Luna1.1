import sys
from datetime import datetime

COLORS = {
    "reset":  "\033[0m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "gray":   "\033[90m",
    "purple": "\033[95m",
}

def c(text, color):
    return f"{COLORS.get(color,'')}{text}{COLORS['reset']}"

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "info":    c(f"[{ts}] ✓", "green"),
        "step":    c(f"[{ts}] →", "cyan"),
        "warn":    c(f"[{ts}] !", "yellow"),
        "error":   c(f"[{ts}] ✗", "red"),
        "section": c(f"[{ts}] ◆", "purple"),
    }.get(level, c(f"[{ts}]", "gray"))
    print(f"{prefix} {msg}")

def banner():
    art = f"""
{c('  _                         _   _ ', 'purple')}
{c(' | |    _   _ _ __   __ _  / | / |', 'purple')}
{c(' | |   | | | | \'_ \\ / _` | | | | |', 'purple')}
{c(' | |___| |_| | | | | (_| | | |_| |', 'purple')}
{c(' |_____|\\__,_|_| |_|\\__,_| |_(_)_|', 'purple')}
{c('', 'purple')}
{c('  AI Creative Studio v1.1  ·  image · video · tts · music · studio', 'gray')}
{c('  github.com/yourusername/luna11', 'gray')}
"""
    print(art)
