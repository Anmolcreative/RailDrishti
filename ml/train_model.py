"""Train a LightGBM multi-class recommendation model for RailDrishti."""

import json
from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

from feature_engineering import FEATURE_COLUMNS, CATEGORICAL_COLUMNS, ACTION_ORDER, build_features, save_feature_schema

MODEL_DIR = Path(__file__).resolve().parent / "model"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_FILE = MODEL_DIR / "lightgbm_recommender.pkl"
LABEL_ENCODER_FILE = MODEL_DIR / "label_encoder.pkl"
FEATURE_SCHEMA_FILE = MODEL_DIR / "feature_schema.json"
METRICS_FILE = MODEL_DIR / "training_metrics.json"


def train_model(
    raw_path: Path = None,
    model_path: Path = MODEL_FILE,
    label_encoder_path: Path = LABEL_ENCODER_FILE,
    schema_path: Path = FEATURE_SCHEMA_FILE,
    metrics_path: Path = METRICS_FILE,
) -> dict:
    df = pd.read_csv(raw_path) if raw_path is not None else pd.read_csv(Path(__file__).resolve().parent / "data" / "synthetic_delays.csv")
    X, y = build_features(df)

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=0.20,
        stratify=y,
        random_state=42,
    )

    model = lgb.LGBMClassifier(
        objective="multiclass",
        num_class=len(ACTION_ORDER),
        learning_rate=0.05,
        num_leaves=31,
        n_estimators=250,
        random_state=42,
        importance_type="gain",
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="multi_logloss",
        callbacks=[lgb.early_stopping(20)],
        categorical_feature=CATEGORICAL_COLUMNS,
    )

    predictions = model.predict(X_val)
    probabilities = model.predict_proba(X_val)
    top_confidence = probabilities.max(axis=1).mean()

    report = classification_report(y_val, predictions, output_dict=True, zero_division=0)
    metrics = {
        "accuracy": float(accuracy_score(y_val, predictions)),
        "average_confidence": float(top_confidence),
        "classification_report": report,
    }

    joblib.dump(model, model_path)
    joblib.dump(y.cat.categories.tolist(), label_encoder_path)
    save_feature_schema(schema_path)

    with open(metrics_path, "w", encoding="utf-8") as fp:
        json.dump(metrics, fp, indent=2)

    return metrics


if __name__ == "__main__":
    results = train_model()
    print("LightGBM model trained and saved to:")
    print(f"  model: {MODEL_FILE}")
    print(f"  schema: {FEATURE_SCHEMA_FILE}")
    print(f"  metrics: {METRICS_FILE}")
    print(json.dumps(results, indent=2))
