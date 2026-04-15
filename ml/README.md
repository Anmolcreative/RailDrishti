# RailDrishti ML module

This folder contains RailDrishti model training and inference utilities for the LightGBM recommendation pipeline.

## Key files

- `feature_engineering.py` — builds tabular features and target labels from synthetic delay data.
- `train_model.py` — trains and saves a LightGBM multiclass recommendation model.
- `inference_server.py` — FastAPI service for serving model predictions.
- `train_pipeline.py` — orchestrates GNN, LightGBM, and PPO training flows.

## Usage

Train the LightGBM model:

```bash
python train_model.py
```

Run the FastAPI inference server:

```bash
uvicorn inference_server:app --host 0.0.0.0 --port 8000
```

Test the prediction endpoint with JSON payloads against `/predict`.
