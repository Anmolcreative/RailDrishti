"""
RailDrishti — LightGBM Training Script
Optuna-tuned multiclass classifier: APPROVE / HOLD / REROUTE / PRIORITY_OVERRIDE
Exports: lightgbm_recommender.pkl, label_encoder.pkl, training_metrics.json
"""

import json
import logging
import pickle
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import optuna
import shap
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import LabelEncoder

from feature_engineering import FEATURE_NAMES, generate_synthetic_dataset

warnings.filterwarnings("ignore", category=UserWarning)
optuna.logging.set_verbosity(optuna.logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("raildrishti.train")

# ── Paths ─────────────────────────────────────────────────────────────────────
MODEL_DIR    = Path("ml/model")
DATA_DIR     = Path("ml/data/processed")
FEATURES_PATH = DATA_DIR / "features.parquet"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

ACTION_LABELS = ["APPROVE", "HOLD", "REROUTE", "PRIORITY_OVERRIDE"]


# ── Data loading ──────────────────────────────────────────────────────────────
def load_or_generate(n_samples: int = 100_000) -> tuple:
    import pandas as pd

    if FEATURES_PATH.exists():
        log.info("Loading features from %s …", FEATURES_PATH)
        df = pd.read_parquet(FEATURES_PATH)
    else:
        log.info("No features file found. Generating synthetic dataset (%d samples) …", n_samples)
        df = generate_synthetic_dataset(n_samples)
        df.to_parquet(FEATURES_PATH, index=False)
        log.info("Saved → %s", FEATURES_PATH)

    X = df[FEATURE_NAMES].values
    y = df["label"].values.astype(int)

    log.info("Dataset shape: X=%s | Classes: %s", X.shape, dict(zip(*np.unique(y, return_counts=True))))
    return X, y


# ── Optuna objective ──────────────────────────────────────────────────────────
def make_objective(X_train, y_train, n_folds: int = 5):
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "objective":        "multiclass",
            "num_class":        4,
            "metric":           "multi_logloss",
            "verbosity":        -1,
            "boosting_type":    "gbdt",
            "n_estimators":     trial.suggest_int("n_estimators",    100, 800),
            "learning_rate":    trial.suggest_float("learning_rate",  0.01, 0.3, log=True),
            "num_leaves":       trial.suggest_int("num_leaves",       20, 150),
            "max_depth":        trial.suggest_int("max_depth",        3, 12),
            "min_child_samples":trial.suggest_int("min_child_samples",10, 80),
            "subsample":        trial.suggest_float("subsample",      0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree",0.5, 1.0),
            "reg_alpha":        trial.suggest_float("reg_alpha",      1e-4, 1.0, log=True),
            "reg_lambda":       trial.suggest_float("reg_lambda",     1e-4, 1.0, log=True),
            "class_weight":     "balanced",
            "random_state":     42,
            "n_jobs":           -1,
        }

        f1_scores = []
        for fold, (tr_idx, val_idx) in enumerate(skf.split(X_train, y_train)):
            model = lgb.LGBMClassifier(**params)
            model.fit(
                X_train[tr_idx], y_train[tr_idx],
                eval_set=[(X_train[val_idx], y_train[val_idx])],
                callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)],
            )
            preds = model.predict(X_train[val_idx])
            f1_scores.append(f1_score(y_train[val_idx], preds, average="macro"))

        return float(np.mean(f1_scores))

    return objective


# ── Training ──────────────────────────────────────────────────────────────────
def train(n_trials: int = 100, n_samples: int = 100_000):
    X, y = load_or_generate(n_samples)

    # Split: 70 / 15 / 15 stratified
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.15, stratify=y, random_state=42
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.1765, stratify=y_trainval, random_state=42
    )
    log.info("Train: %d | Val: %d | Test: %d", len(X_train), len(X_val), len(X_test))

    # ── Optuna search ─────────────────────────────────────────────────────────
    log.info("Starting Optuna hyperparameter search (%d trials, 5-fold CV) …", n_trials)
    study = optuna.create_study(direction="maximize", study_name="raildrishti_lgbm")
    study.optimize(make_objective(X_train, y_train), n_trials=n_trials, show_progress_bar=True)

    best = study.best_params
    log.info("Best CV macro-F1: %.4f | Params: %s", study.best_value, best)

    # ── Final model on full train+val ─────────────────────────────────────────
    final_params = {
        "objective":        "multiclass",
        "num_class":        4,
        "metric":           "multi_logloss",
        "verbosity":        -1,
        "class_weight":     "balanced",
        "random_state":     42,
        "n_jobs":           -1,
        **best,
    }
    log.info("Training final model on train+val …")
    final_model = lgb.LGBMClassifier(**final_params)
    final_model.fit(
        X_trainval, y_trainval,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(50)],
    )

    # ── Evaluation ────────────────────────────────────────────────────────────
    y_pred_val  = final_model.predict(X_val)
    y_pred_test = final_model.predict(X_test)

    val_f1  = f1_score(y_val,  y_pred_val,  average="macro")
    test_f1 = f1_score(y_test, y_pred_test, average="macro")

    log.info("Val  macro-F1: %.4f", val_f1)
    log.info("Test macro-F1: %.4f", test_f1)
    print("\nTest Classification Report:")
    print(classification_report(y_test, y_pred_test, target_names=ACTION_LABELS))
    print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred_test))

    # ── SHAP feature importance ───────────────────────────────────────────────
    log.info("Computing SHAP values on test set (subsample 500 rows) …")
    explainer   = shap.TreeExplainer(final_model)
    shap_values = explainer.shap_values(X_test[:500])
    # Mean |SHAP| per feature across all classes
    mean_shap   = np.mean([np.abs(sv).mean(axis=0) for sv in shap_values], axis=0)
    shap_importance = sorted(
        zip(FEATURE_NAMES, mean_shap.tolist()),
        key=lambda x: x[1], reverse=True,
    )
    log.info("Top 5 SHAP features: %s", shap_importance[:5])

    # ── Label encoder (int → string) ──────────────────────────────────────────
    le = LabelEncoder()
    le.fit(ACTION_LABELS)

    # ── Persist artifacts ─────────────────────────────────────────────────────
    model_path   = MODEL_DIR / "lightgbm_recommender.pkl"
    encoder_path = MODEL_DIR / "label_encoder.pkl"
    metrics_path = MODEL_DIR / "training_metrics.json"
    schema_path  = MODEL_DIR / "feature_schema.json"

    with open(model_path, "wb") as f:
        pickle.dump(final_model, f)
    log.info("Model saved → %s", model_path)

    with open(encoder_path, "wb") as f:
        pickle.dump(le, f)
    log.info("Label encoder saved → %s", encoder_path)

    metrics = {
        "val_macro_f1":         round(val_f1, 4),
        "test_macro_f1":        round(test_f1, 4),
        "best_optuna_cv_f1":    round(study.best_value, 4),
        "n_optuna_trials":      n_trials,
        "best_hyperparams":     best,
        "shap_feature_importance": [
            {"feature": f, "mean_abs_shap": round(v, 4)} for f, v in shap_importance
        ],
        "train_samples":        int(len(X_train)),
        "val_samples":          int(len(X_val)),
        "test_samples":         int(len(X_test)),
        "action_labels":        ACTION_LABELS,
        "feature_names":        FEATURE_NAMES,
    }
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    log.info("Metrics saved → %s", metrics_path)

    schema = {"feature_names": FEATURE_NAMES, "n_features": len(FEATURE_NAMES)}
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=2)
    log.info("Feature schema saved → %s", schema_path)

    return final_model, metrics


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train RailDrishti LightGBM model")
    parser.add_argument("--trials",  type=int, default=100, help="Optuna trials (default 100)")
    parser.add_argument("--samples", type=int, default=100_000, help="Synthetic samples if no real data")
    args = parser.parse_args()

    train(n_trials=args.trials, n_samples=args.samples)
