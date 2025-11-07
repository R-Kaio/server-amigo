import os
import asyncio
import json
from datetime import datetime
from typing import Set, Optional

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

HOST = os.getenv("WS_HOST", "0.0.0.0")
PORT = int(os.getenv("WS_PORT", "8080"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
UPDATE_INTERVAL = float(os.getenv("UPDATE_INTERVAL", "2"))
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "localhost")
PUBLIC_PORT = os.getenv("PUBLIC_PORT", str(PORT))
USE_WSS = os.getenv("USE_WSS", "false").lower() in ("1", "true", "yes")

psutil.cpu_percent(interval=None)
last_io_stats = psutil.disk_io_counters()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(__file__)       
STATIC_DIR = os.path.join(BASE_DIR, "static")  
os.makedirs(STATIC_DIR, exist_ok=True)

scripts_dir = os.path.join(STATIC_DIR, "scripts")
styles_dir = os.path.join(STATIC_DIR, "styles")
assets_dir = os.path.join(STATIC_DIR, "assets")

if os.path.isdir(scripts_dir):
    app.mount("/scripts", StaticFiles(directory=scripts_dir), name="scripts")
if os.path.isdir(styles_dir):
    app.mount("/styles", StaticFiles(directory=styles_dir), name="styles")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

INDEX_PATH = os.path.join(STATIC_DIR, "index.html")
@app.get("/")
async def root_index():
    if os.path.isfile(INDEX_PATH):
        return FileResponse(INDEX_PATH, media_type="text/html")
    return JSONResponse({"error": "index.html not found"}, status_code=404)

clients: Set[WebSocket] = set()
broadcast_task: Optional[asyncio.Task] = None
broadcast_lock = asyncio.Lock()


def get_metrics():
    """Collect system metrics using psutil."""
    global last_io_stats
    try:
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage("/").percent
        current_io_stats = psutil.disk_io_counters()

        read_bytes = current_io_stats.read_bytes - last_io_stats.read_bytes
        write_bytes = current_io_stats.write_bytes - last_io_stats.write_bytes

        read_speed = read_bytes / UPDATE_INTERVAL
        write_speed = write_bytes / UPDATE_INTERVAL

        last_io_stats = current_io_stats

        return {
            "cpu": round(cpu, 2),
            "memory": round(memory, 2),
            "disk": round(disk_usage, 2),
            "disk_read": round(read_speed, 2),
            "disk_write": round(write_speed, 2),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "cpu": 0,
            "memory": 0,
            "disk": 0,
            "disk_read": 0,
            "disk_write": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def broadcast_metrics_loop():
    """Background task that periodically broadcasts metrics to connected clients."""
    try:
        while True:
            await asyncio.sleep(UPDATE_INTERVAL)
            if not clients:
                continue
            metrics = get_metrics()
            message = json.dumps(metrics)
            send_coros = [safe_send(ws, message) for ws in list(clients)]
            results = await asyncio.gather(*send_coros, return_exceptions=True)
            for ws, res in zip(list(clients), results):
                if isinstance(res, Exception):
                    try:
                        await ws.close()
                    except Exception:
                        pass
                    clients.discard(ws)
    except asyncio.CancelledError:
        return


async def safe_send(ws: WebSocket, message: str):
    """Send a message to a websocket, raising on failure so caller can handle removal."""
    await ws.send_text(message)


@app.on_event("startup")
async def on_startup():
    """Start the broadcast task on app startup."""
    global broadcast_task
    async with broadcast_lock:
        if broadcast_task is None or broadcast_task.done():
            broadcast_task = asyncio.create_task(broadcast_metrics_loop())
    print("=" * 60)
    print("Servidor WebSocket + Frontend (FastAPI) iniciado")
    scheme = "wss" if USE_WSS else "ws"
    print(f"Endereço WS: {scheme}://{PUBLIC_HOST}:{PUBLIC_PORT}/ws/metrics")
    print(f"Origens permitidas: {', '.join(ALLOWED_ORIGINS)}")
    print(f"Intervalo de atualização: {UPDATE_INTERVAL}s")
    print("=" * 60)


@app.on_event("shutdown")
async def on_shutdown():
    """Cancel broadcast task on shutdown and close client connections."""
    global broadcast_task
    if broadcast_task:
        broadcast_task.cancel()
        try:
            await broadcast_task
        except Exception:
            pass
    for ws in list(clients):
        try:
            await ws.close()
        except Exception:
            pass
    clients.clear()


@app.websocket("/ws/metrics")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint that registers clients and keeps connection alive."""
    await websocket.accept()
    client_info = f"{getattr(websocket.client, 'host', 'unknown')}:{getattr(websocket.client, 'port', '?')}"
    print(f'[{datetime.now().strftime("%H:%M:%S")}] Cliente conectado: {client_info}')
    clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in clients:
            clients.discard(websocket)
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Cliente desconectado: {client_info}')


@app.get("/config.json")
async def config():
    """Return the WebSocket URL for the frontend to fetch dynamically (used by client init)."""
    scheme = "wss" if USE_WSS else "ws"
    ws_url = f"{scheme}://{PUBLIC_HOST}:{PUBLIC_PORT}/ws/metrics"
    return JSONResponse({"wsUrl": ws_url})
