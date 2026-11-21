from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from features import (
    CATEGORICAL_FEATURES, FEATURE_COLUMNS, NUMERIC_FEATURES,
    add_features, load_dataset,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data/raw/dengue_dataset.xlsx"
DEFAULT_MODEL_DIR = ROOT / "models"


def build_pipeline(model_name: str = "random_forest") -> Pipeline:
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    categorical = Pipeline([("imputer", SimpleImputer(strategy="most_frequent")),
                            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    preprocess = ColumnTransformer([
        ("num", numeric, NUMERIC_FEATURES),
        ("cat", categorical, CATEGORICAL_FEATURES),
    ])
    if model_name == "hist_gradient_boosting":
        estimator = HistGradientBoostingRegressor(
            max_iter=160, learning_rate=0.07, max_leaf_nodes=20,
            l2_regularization=1.0, random_state=42,
        )
    else:
        estimator = RandomForestRegressor(
            n_estimators=100, max_depth=14, min_samples_leaf=3,
            max_features=0.75, n_jobs=2, random_state=42,
        )
    return Pipeline([("preprocess", preprocess), ("model", estimator)])


def metrics(y_true, y_pred) -> dict:
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "samples": int(len(y_true)),
    }


def temporal_split(frame: pd.DataFrame, horizon: int):
    target_date = frame[f"target_date_{horizon}w"]
    train_mask = target_date < pd.Timestamp("2024-01-01")
    val_mask = (target_date >= pd.Timestamp("2024-01-01")) & (target_date < pd.Timestamp("2025-01-01"))
    test_mask = (target_date >= pd.Timestamp("2025-01-01")) & (target_date < pd.Timestamp("2026-01-01"))
    return train_mask, val_mask, test_mask


def train_one(frame: pd.DataFrame, horizon: int, model_dir: Path) -> dict:
    target = f"target_{horizon}w"
    target_date = f"target_date_{horizon}w"
    usable = frame.dropna(subset=FEATURE_COLUMNS + [target, target_date]).copy()
    train_mask, val_mask, test_mask = temporal_split(usable, horizon)
    train = usable.loc[train_mask]
    val = usable.loc[val_mask]
    test = usable.loc[test_mask]
    if min(len(train), len(val), len(test)) == 0:
        raise RuntimeError(f"Insufficient temporal split data for {horizon}-week model")

    X_train, y_train = train[FEATURE_COLUMNS], train[target].clip(lower=0)
    X_val, y_val = val[FEATURE_COLUMNS], val[target].clip(lower=0)
    X_test, y_test = test[FEATURE_COLUMNS], test[target].clip(lower=0)

    candidates = {}
    for name in ["random_forest"]:
        model = build_pipeline(name)
        model.fit(X_train, y_train)
        candidates[name] = (model, metrics(y_val, np.maximum(0, model.predict(X_val))))

    selected_name = min(candidates, key=lambda name: candidates[name][1]["mae"])
    selected_model = candidates[selected_name][0]
    test_metrics = metrics(y_test, np.maximum(0, selected_model.predict(X_test)))
    baseline = DummyRegressor(strategy="median").fit(X_train, y_train)
    baseline_metrics = metrics(y_test, np.maximum(0, baseline.predict(X_test)))

    # Data-derived risk thresholds from training targets only; never use test labels.
    q50, q75, q90 = np.quantile(y_train, [0.50, 0.75, 0.90]).tolist()
    thresholds = {"low_max": round(float(q50), 3),
                  "medium_max": round(float(q75), 3),
                  "high_max": round(float(q90), 3)}

    model_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": selected_model,
        "horizon_weeks": horizon,
        "feature_columns": FEATURE_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "risk_thresholds": thresholds,
        "metrics": {
            "selected_model": selected_name,
            "validation": candidates[selected_name][1],
            "test": test_metrics,
            "baseline_test": baseline_metrics,
            "train_rows": int(len(train)),
            "validation_rows": int(len(val)),
            "test_rows": int(len(test)),
            "train_target_date_end": str(train[target_date].max().date()),
            "validation_target_date_range": [str(val[target_date].min().date()), str(val[target_date].max().date())],
            "test_target_date_range": [str(test[target_date].min().date()), str(test[target_date].max().date())],
        },
    }
    joblib.dump(artifact, model_dir / f"dengue_{horizon}week.joblib")
    return artifact["metrics"] | {"risk_thresholds": thresholds, "model": selected_name}


def main():
    parser = argparse.ArgumentParser(description="Train DengueShield ward-level early-warning models")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    args = parser.parse_args()

    df = load_dataset(args.data)
    features = add_features(df, include_targets=True)
    model_dir = Path(args.model_dir)
    results = {str(h): train_one(features, h, model_dir) for h in (2, 4)}
    metadata = {
        "dataset_rows": int(len(df)),
        "dataset_columns": int(len(df.columns)),
        "date_start": str(df.date.min().date()),
        "date_end": str(df.date.max().date()),
        "cities": sorted(df.city.unique().tolist()),
        "wards": int(df.ward_id.nunique()),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_ward_dates": int(df.duplicated(["date", "ward_id"]).sum()),
        "models": results,
    }
    (model_dir / "training_metrics.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
