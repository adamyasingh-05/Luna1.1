from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.responses import HTMLResponse
import subprocess
import asyncio
from pathlib import Path
import uuid
import json

app = FastAPI(title="Luna1.1 AI Studio")

active_tasks = {}

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    while task_id in active_tasks:
        task = active_tasks[task_id]
        await websocket.send_json({
            "progress": task.get("progress", 0),
            "log": task.get("log", ""),
            "status": task.get("status", "running")
        })
        await asyncio.sleep(0.3)
    await websocket.close()

def run_task(task_id: str, cmd: list):
    active_tasks[task_id] = {"progress": 0, "log": "Starting...", "status": "running"}
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(Path(__file__).parent))
    
    output = ""
    for line in iter(process.stdout.readline, ''):
        output += line
        active_tasks[task_id]["log"] = output[-600:]
        if "inference" in line.lower() or "generat" in line.lower():
            active_tasks[task_id]["progress"] = min(95, active_tasks[task_id]["progress"] + 12)
    active_tasks[task_id]["status"] = "completed"
    active_tasks[task_id]["progress"] = 100

@app.post("/generate/image")
async def generate_image(prompt: str, style: str = "cinematic", background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(run_task, task_id, ["python", "main.py", "image", prompt, "--style", style])
    return {"task_id": task_id, "ws_url": f"/ws/{task_id}"}

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Luna1.1 Live</title></head>
    <body>
        <h1>Luna1.1 — Live Generation</h1>
        <input id="prompt" placeholder="Enter prompt" style="width:400px">
        <button onclick="startGeneration()">Generate Image</button>
        <div id="status"></div>
        <pre id="log"></pre>

        <script>
            let ws;
            async function startGeneration() {
                const prompt = document.getElementById('prompt').value;
                const res = await fetch(`/generate/image?prompt=${encodeURIComponent(prompt)}`);
                const data = await res.json();
                
                document.getElementById('status').innerHTML = `Task ${data.task_id} started`;
                
                ws = new WebSocket(`ws://localhost:8000/ws/${data.task_id}`);
                ws.onmessage = (event) => {
                    const d = JSON.parse(event.data);
                    document.getElementById('log').textContent = d.log;
                    // Progress bar can be added here
                };
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)