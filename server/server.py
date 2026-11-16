import os
import sys

# Force UTF-8 standard output so Japanese text prints safely on Windows
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import asyncio
from contextlib import asynccontextmanager

# Ensure imports from current directory work cleanly even if run from root path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Relative imports for package modules
from . import idle_animator
from . import chat_handler

# Create the lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [STARTUP]
    loop = asyncio.get_running_loop()
    idle_animator.start_animator(loop)
    chat_handler.start_watchdog(loop)
    
    yield  # The server runs while paused here
    
    # [SHUTDOWN]
    chat_handler.stop_watchdog()
    idle_animator.stop_animator()

# Get parent workspace directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Initialize fastapi app with lifespan
app = FastAPI(lifespan=lifespan)

# Serve static files relative to root path to prevent local CORS issues.
# Optional asset directories are mounted only when present, so the server
# boots on a fresh clone that does not include local VRM models or voice samples.
def mount_if_exists(route: str, folder: str):
    path = os.path.join(BASE_DIR, folder)
    if os.path.isdir(path):
        app.mount(route, StaticFiles(directory=path), name=route.strip("/") or folder)
    else:
        print(f"[Visage Link] Skipping mount '{route}': folder '{folder}' not found.")

mount_if_exists("/Models", "Models")
mount_if_exists("/voice sample", "voice sample")
mount_if_exists("/js", "js")
mount_if_exists("/css", "css")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(BASE_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/test-idle-poses", response_class=HTMLResponse)
async def get_test():
    test_path = os.path.join(BASE_DIR, "test_idle_poses.html")
    if not os.path.isfile(test_path):
        return HTMLResponse("<h1>404</h1><p>test_idle_poses.html not found.</p>", status_code=404)
    with open(test_path, "r", encoding="utf-8") as f:
        return f.read()

# Register the chat WebSocket handler
@app.websocket("/ws/chat")
async def chat_route(websocket: WebSocket):
    await chat_handler.handle_chat_session(websocket)

if __name__ == "__main__":
    import uvicorn
    # run with package syntax or direct module string
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
