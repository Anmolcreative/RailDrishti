"""RailDrishti decision maker for comparing Indian Railways baseline actions to model suggestions."""

from typing import Dict

import pandas as pd

from feature_engineering import build_features, FEATURE_COLUMNS


def build_indian_rail_baseline(payload: Dict) -> str:
    """Compute the Indian Railways baseline action for a single train event."""
    df = pd.DataFrame([payload])
    _, target = build_features(df)
    return str(target.iloc[0])


def compare_payload(payload: Dict, predicted_action: str, confidence: float) -> Dict:
    """Compare RailDrishti model suggestion against Indian Railways baseline."""
    indian_action = build_indian_rail_baseline(payload)
    match = predicted_action == indian_action
    return {
        "train_id": payload.get("train_id", ""),
        "raildrishti_action": predicted_action,
        "indian_rail_action": indian_action,
        "confidence": confidence,
        "match": match,
        "difference": "same" if match else f"rail_drishhti:{predicted_action} vs indian_rail:{indian_action}",
    }
