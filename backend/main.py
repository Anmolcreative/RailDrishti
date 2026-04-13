from fastapi  import FastAPI,WebSocket
from routes.trains import router 
import asyncio
import json

app = FastAPI(title="RailDrishti API")
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "RailDrishti backend is running smoothly!"}

@app.websocket("/ws/live")              # ← add everything below
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = { 
                "trains": [
                {"id": "TN001", "lat": 19.0760, "lng": 72.8777, "speed": 60, "delay": 5, "status": "on time"},
                {"id": "TN002", "lat": 28.6139, "lng": 77.2090, "speed": 80, "delay": 0 , "status": "on time"},
                {"id": "TN003", "lat": 13.0827, "lng": 80.2707, "speed": 45, "delay": 12, "status": "delayed"}
                ]
            }
            await websocket.send_json(data)
            await asyncio.sleep(1)
    except Exception:
        await websocket.close()


