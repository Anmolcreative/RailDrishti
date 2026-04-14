from fastapi  import FastAPI,WebSocket
from routes.trains import router,TRAINS
import asyncio
import json 

app = FastAPI(title="RailDrishti API")
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "RailDrishti backend is running smoothly!"}

@app.websocket("/ws/live")              
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"trains": TRAINS})
            await asyncio.sleep(2)
    except Exception:
        await websocket.close()


