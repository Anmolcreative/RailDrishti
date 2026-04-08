from fastapi  import FastAPI
from routes.trains import router 
app = FastAPI(title="RailDrishti API")
app.include_router(router)
@app.get("/health")
def health():
    return {"status": "RailDrishti backend is running smoothly!"}

