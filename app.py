import streamlit as st
import subprocess
import threading
import queue
import time
import os
from pathlib import Path
import uuid

WORKDIR = str(Path(__file__).parent)

st.set_page_config(page_title="Luna1.1 AI Creative Studio", page_icon="🎨", layout="wide")

st.markdown("""
<style>
    .main { background-color: #ffffff; }
    .header { font-size: 2.8rem; font-weight: 700; text-align: center; color: #111827; }
    .log { font-family: monospace; background: #f8fafc; padding: 1rem; border-radius: 8px; max-height: 400px; overflow-y: auto; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='header'>Luna1.1 AI Creative Studio</div>", unsafe_allow_html=True)

# Session State
if 'tasks' not in st.session_state:
    st.session_state.tasks = {}
if 'task_queue' not in st.session_state:
    st.session_state.task_queue = queue.Queue()

def background_worker():
    while True:
        task = st.session_state.task_queue.get()
        if task is None:
            break
        task_id = task['id']
        try:
            st.session_state.tasks[task_id]['status'] = 'running'
            process = subprocess.Popen(
                task['cmd'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=WORKDIR
            )
            st.session_state.tasks[task_id]['process'] = process
            output = ""
            progress = 0
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    output += line
                    if any(k in line.lower() for k in ["inference", "generat", "step", "saved"]):
                        progress = min(98, progress + 15)
                    st.session_state.tasks[task_id]['log'] = output[-900:]
                    st.session_state.tasks[task_id]['progress'] = progress
                time.sleep(0.1)
            st.session_state.tasks[task_id]['status'] = 'completed'
            st.session_state.tasks[task_id]['progress'] = 100
        except Exception as e:
            st.session_state.tasks[task_id]['status'] = 'failed'
            st.session_state.tasks[task_id]['log'] = str(e)
        st.session_state.task_queue.task_done()

# Start worker
if 'worker' not in st.session_state:
    threading.Thread(target=background_worker, daemon=True).start()
    st.session_state.worker = True

# ── UI ────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🖼 Image", "🎬 Video", "🔊 TTS", "🎵 Music", "🎬 Studio"])

with tab1:
    st.subheader("Generate Image")
    prompt = st.text_area("Prompt", "futuristic cyberpunk city at sunset", key="img_prompt")
    style = st.selectbox("Style", ["cinematic", "anime", "photorealistic", "artistic", "documentary", "promo"], key="img_style")
    size = st.selectbox("Size", ["1024x1024", "768x768", "512x512"], key="img_size")
    enhance = st.checkbox("Enhance prompt", key="img_enhance")
    if st.button("Queue Image", key="btn_img"):
        tid = str(uuid.uuid4())[:8]
        cmd = ["python", "main.py", "image", prompt, "--style", style, "--size", size]
        if enhance:
            cmd.append("--enhance")
        st.session_state.tasks[tid] = {"type": "image", "status": "queued", "prompt": prompt[:50], "progress": 0, "log": ""}
        st.session_state.task_queue.put({"id": tid, "cmd": cmd})
        st.success(f"Queued! Task ID: {tid}")

with tab2:
    st.subheader("Generate Video")
    prompt = st.text_area("Prompt", "a wolf running through a snowy forest", key="vid_prompt")
    style = st.selectbox("Style", ["cinematic", "anime", "photorealistic", "artistic", "documentary", "promo"], key="vid_style")
    duration = st.slider("Duration (seconds)", 3, 30, 5, key="vid_duration")
    enhance = st.checkbox("Enhance prompt", key="vid_enhance")
    if st.button("Queue Video", key="btn_vid"):
        tid = str(uuid.uuid4())[:8]
        cmd = ["python", "main.py", "video", prompt, "--style", style, "--duration", str(duration)]
        if enhance:
            cmd.append("--enhance")
        st.session_state.tasks[tid] = {"type": "video", "status": "queued", "prompt": prompt[:50], "progress": 0, "log": ""}
        st.session_state.task_queue.put({"id": tid, "cmd": cmd})
        st.success(f"Queued! Task ID: {tid}")

with tab3:
    st.subheader("Text-to-Speech")
    text = st.text_area("Text", "Welcome to Luna1.1. Let's create something amazing.", key="tts_text")
    voice = st.selectbox("Voice", ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "en-AU-NatashaNeural"], key="tts_voice")
    speed = st.select_slider("Speed", options=["-20%", "-10%", "+0%", "+10%", "+20%"], value="+0%", key="tts_speed")
    if st.button("Queue TTS", key="btn_tts"):
        tid = str(uuid.uuid4())[:8]
        cmd = ["python", "main.py", "tts", text, "--voice", voice, "--speed", speed]
        st.session_state.tasks[tid] = {"type": "tts", "status": "queued", "prompt": text[:50], "progress": 0, "log": ""}
        st.session_state.task_queue.put({"id": tid, "cmd": cmd})
        st.success(f"Queued! Task ID: {tid}")

with tab4:
    st.subheader("Generate Music")
    prompt = st.text_area("Prompt", "calm lo-fi hip hop beat, relaxing", key="mus_prompt")
    duration = st.slider("Duration (seconds)", 10, 120, 30, key="mus_duration")
    if st.button("Queue Music", key="btn_mus"):
        tid = str(uuid.uuid4())[:8]
        cmd = ["python", "main.py", "music", prompt, "--duration", str(duration)]
        st.session_state.tasks[tid] = {"type": "music", "status": "queued", "prompt": prompt[:50], "progress": 0, "log": ""}
        st.session_state.task_queue.put({"id": tid, "cmd": cmd})
        st.success(f"Queued! Task ID: {tid}")

with tab5:
    st.subheader("Full Studio Production")
    st.caption("Generates video + voiceover + optional music + captions from one prompt.")
    prompt = st.text_area("Prompt", "a short documentary about deep sea creatures", key="st_prompt")
    style = st.selectbox("Style", ["cinematic", "anime", "photorealistic", "artistic", "documentary", "promo"], key="st_style")
    duration = st.slider("Duration (seconds)", 10, 120, 30, key="st_duration")
    voice = st.selectbox("Voice", ["auto", "en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural"], key="st_voice")
    col1, col2 = st.columns(2)
    with col1:
        music = st.checkbox("Add background music", key="st_music")
    with col2:
        captions = st.checkbox("Add captions", key="st_captions")
    if st.button("Queue Studio Production", key="btn_studio"):
        tid = str(uuid.uuid4())[:8]
        cmd = ["python", "main.py", "studio", prompt, "--style", style, "--duration", str(duration), "--voice", voice]
        if music:
            cmd.append("--music")
        if captions:
            cmd.append("--captions")
        st.session_state.tasks[tid] = {"type": "studio", "status": "queued", "prompt": prompt[:50], "progress": 0, "log": ""}
        st.session_state.task_queue.put({"id": tid, "cmd": cmd})
        st.success(f"Queued! Task ID: {tid}")

# ── Task Monitor ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("Active Tasks")

if not st.session_state.tasks:
    st.info("No tasks yet. Queue something above.")
else:
    for tid, t in st.session_state.tasks.items():
        status_icon = {"queued": "⏳", "running": "⚙️", "completed": "✅", "failed": "❌"}.get(t['status'], "❓")
        with st.expander(f"{status_icon} {tid} — {t['type']} — {t['status']} ({t.get('progress', 0)}%)", expanded=(t['status'] == 'running')):
            st.caption(f"Prompt: {t.get('prompt', '')}")
            if t.get('progress', 0) > 0:
                st.progress(t['progress'] / 100)
            if t.get('log'):
                st.code(t['log'][-600:], language="")

if st.button("Clear completed tasks"):
    st.session_state.tasks = {k: v for k, v in st.session_state.tasks.items() if v['status'] not in ('completed', 'failed')}
    st.rerun()
