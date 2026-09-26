import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import os

# Environment variables for configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Global Redis client
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to Redis
    global redis_client
    redis_client = redis.from_url(REDIS_URL)
    print("✅ Connected to Redis Event Bus")
    yield
    # Shutdown: Disconnect Redis
    await redis_client.close()
    print("❌ Disconnected from Redis")

app = FastAPI(title="IBVAP Core Backend", lifespan=lifespan)

# Allow dashboard to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "ok", "service": "IBVAP Core Backend"}

# --- Event Bus (Redis) Endpoints ---
# Modules will publish to Redis. The dashboard will subscribe to this WebSocket
# to receive live events (e.g. alerts).

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    Dashboard connects here to receive real-time alerts.
    We subscribe to the 'alerts' Redis channel and forward messages.
    """
    await manager.connect(websocket)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("ibvap_alerts")
    
    try:
        # A simple task to forward redis messages to the websocket
        async def redis_to_ws():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"].decode("utf-8")
                    await manager.broadcast(data)
        
        # Run listening loop
        task = asyncio.create_task(redis_to_ws())
        
        # Keep connection open
        while True:
            # We don't expect client to send much, but we must handle receive
            _ = await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await pubsub.unsubscribe("ibvap_alerts")
        task.cancel()
