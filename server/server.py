import os
import sys
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

# Serve static files relative to root path to prevent local CORS issues
app.mount("/Models", StaticFiles(directory=os.path.join(BASE_DIR, "Models")), name="Models")
app.mount("/voice sample", StaticFiles(directory=os.path.join(BASE_DIR, "voice sample")), name="voice sample")
app.mount("/js", StaticFiles(directory=os.path.join(BASE_DIR, "js")), name="js")
app.mount("/css", StaticFiles(directory=os.path.join(BASE_DIR, "css")), name="css")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(BASE_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/test-idle-poses", response_class=HTMLResponse)
async def get_test():
    test_path = os.path.join(BASE_DIR, "test_idle_poses.html")
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
