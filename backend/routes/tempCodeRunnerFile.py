from fastapi import APIRouter

router = APIRouter()

@router.get("/trains")
def get_trains():
    return [
        {"train_id": "TN001", "lat": 19.0760, "lng": 72.8777, "speed": 60, "delay": 5},
        {"train_id": "TN002", "lat": 28.6139, "lng": 77.2090, "speed": 80, "delay": 0},
        {"train_id": "TN003", "lat": 13.0827, "lng": 80.2707, "speed": 45, "delay": 12}
    ]

@router.post("/optimize")
def optimize():
    return {"status": "optimization triggered", "model": "GNN+PPO"}