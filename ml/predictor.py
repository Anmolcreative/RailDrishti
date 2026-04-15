"""Shared LightGBM prediction utilities for RailDrishti."""

from pathlib import Path
from typing import Dict, List

import joblib
import pandas as pd

from feature_engineering import build_inference_features, build_features, FEATURE_COLUMNS
from decision_maker import compare_payload as compare_with_indian_rail

MODEL_DIR = Path(__file__).resolve().parent / "model"
MODEL_FILE = MODEL_DIR / "lightgbm_recommender.pkl"
LABEL_ENCODER_FILE = MODEL_DIR / "label_encoder.pkl"
_model = None
_label_categories = []


def load_model(model_path: Path = None, label_path: Path = None) -> None:
    global _model, _label_categories
    if model_path is None:
        model_path = MODEL_FILE
    if label_path is None:
        label_path = LABEL_ENCODER_FILE

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not label_path.exists():
        raise FileNotFoundError(f"Label file not found: {label_path}")

    _model = joblib.load(model_path)
    _label_categories = joblib.load(label_path)


def get_model() -> object:
    if _model is None:
        load_model()
    return _model


def get_label_categories() -> List[str]:
    if not _label_categories:
        load_model()
    return _label_categories


def predict_payload(payload: Dict) -> Dict:
    model = get_model()
    label_categories = get_label_categories()

    features = build_inference_features(payload)
    X = features[FEATURE_COLUMNS]

    probabilities = model.predict_proba(X)[0].tolist()
    predicted_action = str(model.predict(X)[0])
    confidence = float(max(probabilities))

    feature_importances = getattr(model, "feature_importances_", None)
    shap_top5 = []
    if feature_importances is not None:
        names = model.booster_.feature_name() if hasattr(model, "booster_") else X.columns.tolist()
        ranked = sorted(zip(names, feature_importances), key=lambda item: item[1], reverse=True)
        shap_top5 = [name for name, _ in ranked[:5]]

    return {
        "train_id": payload.get("train_id", ""),
        "predicted_action": predicted_action,
        "confidence": confidence,
        "shap_top5": shap_top5,
    }


def compare_payload(payload: Dict) -> Dict:
    model = get_model()
    label_categories = get_label_categories()

    features = build_inference_features(payload)
    X = features[FEATURE_COLUMNS]

    probabilities = model.predict_proba(X)[0].tolist()
    predicted_action = str(model.predict(X)[0])
    confidence = float(max(probabilities))

    comparison = compare_with_indian_rail(payload, predicted_action, confidence)
    comparison["shap_top5"] = []

    feature_importances = getattr(model, "feature_importances_", None)
    if feature_importances is not None:
        names = model.booster_.feature_name() if hasattr(model, "booster_") else X.columns.tolist()
        ranked = sorted(zip(names, feature_importances), key=lambda item: item[1], reverse=True)
        comparison["shap_top5"] = [name for name, _ in ranked[:5]]

    return comparison
