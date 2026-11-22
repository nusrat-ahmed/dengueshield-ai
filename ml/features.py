from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

REQUIRED_COLUMNS = [
    "date", "city", "ward_id", "population_density_sqkm",
    "water_logging_risk_index", "sanitation_score", "avg_temp_c",
    "max_temp_c", "min_temp_c", "rainfall_mm",
    "relative_humidity_pct", "dengue_cases",
]

NUMERIC_BASE = [
    "population_density_sqkm", "water_logging_risk_index", "sanitation_score",
    "avg_temp_c", "max_temp_c", "min_temp_c", "rainfall_mm",
    "relative_humidity_pct",
]

LAG_FEATURES = [
    "rainfall_lag_1", "rainfall_lag_2", "rainfall_lag_3", "rainfall_lag_4",
    "rainfall_sum_2w", "rainfall_sum_4w", "avg_temp_lag_1",
    "humidity_lag_1", "dengue_cases_lag_1", "dengue_cases_lag_2",
    "dengue_cases_mean_4w", "week_sin", "week_cos",
]

NUMERIC_FEATURES = NUMERIC_BASE + LAG_FEATURES
CATEGORICAL_FEATURES = ["city", "ward_id"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def load_dataset(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError("Dataset must be an .xlsx or .csv file")

    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    df = df[REQUIRED_COLUMNS].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isna().any():
        raise ValueError("Dataset contains invalid dates")

    for col in NUMERIC_BASE + ["dengue_cases"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[NUMERIC_BASE + ["dengue_cases"]].isna().any().any():
        raise ValueError("Dataset contains missing or non-numeric values in required numeric columns")

    df["city"] = df["city"].astype(str).str.strip()
    df["ward_id"] = df["ward_id"].astype(str).str.strip()
    if df.duplicated(["date", "ward_id"]).any():
        raise ValueError("Dataset contains duplicate date + ward_id records")

    return df.sort_values(["ward_id", "date"]).reset_index(drop=True)


def add_features(df: pd.DataFrame, include_targets: bool = False) -> pd.DataFrame:
    """Create leakage-aware, ward-grouped historical features.

    All lag/rolling features use current and past observations only. Targets are
    shifted forward within each ward and target_date is retained for temporal splits.
    """
    out = df.copy().sort_values(["ward_id", "date"]).reset_index(drop=True)
    grouped = out.groupby("ward_id", sort=False)

    for lag in range(1, 5):
        out[f"rainfall_lag_{lag}"] = grouped["rainfall_mm"].shift(lag)
    out["rainfall_sum_2w"] = out["rainfall_mm"] + out["rainfall_lag_1"]
    out["rainfall_sum_4w"] = (
        out["rainfall_mm"] + out["rainfall_lag_1"]
        + out["rainfall_lag_2"] + out["rainfall_lag_3"]
    )
    out["avg_temp_lag_1"] = grouped["avg_temp_c"].shift(1)
    out["humidity_lag_1"] = grouped["relative_humidity_pct"].shift(1)
    out["dengue_cases_lag_1"] = grouped["dengue_cases"].shift(1)
    out["dengue_cases_lag_2"] = grouped["dengue_cases"].shift(2)
    out["dengue_cases_mean_4w"] = grouped["dengue_cases"].transform(
        lambda s: s.rolling(window=4, min_periods=4).mean()
    )

    week = out["date"].dt.isocalendar().week.astype(int)
    out["week_sin"] = __import__("numpy").sin(2 * __import__("numpy").pi * week / 52.0)
    out["week_cos"] = __import__("numpy").cos(2 * __import__("numpy").pi * week / 52.0)

    if include_targets:
        out["target_2w"] = grouped["dengue_cases"].shift(-2)
        out["target_4w"] = grouped["dengue_cases"].shift(-4)
        out["target_date_2w"] = grouped["date"].shift(-2)
        out["target_date_4w"] = grouped["date"].shift(-4)

    return out


def feature_row_for_prediction(
    df: pd.DataFrame,
    ward_id: str,
    as_of_date: str | pd.Timestamp | None = None,
    weather_override: dict | None = None,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Return the latest valid feature row for one ward, optionally scenario-adjusted."""
    ward = df[df["ward_id"] == ward_id].copy().sort_values("date")
    if ward.empty:
        raise ValueError(f"Unknown ward_id: {ward_id}")

    if as_of_date is not None:
        requested = pd.Timestamp(as_of_date)
        ward = ward[ward["date"] <= requested]
        if ward.empty:
            raise ValueError("No historical observations exist on or before the selected date")

    engineered = add_features(ward, include_targets=False)
    valid = engineered.dropna(subset=FEATURE_COLUMNS)
    if valid.empty:
        raise ValueError("Not enough historical observations to create four-week lag features")

    row = valid.iloc[[-1]].copy()
    if weather_override:
        allowed = {"avg_temp_c", "rainfall_mm", "relative_humidity_pct"}
        for key, value in weather_override.items():
            if key in allowed and value is not None:
                row.loc[:, key] = float(value)
        # Recalculate current-week derived weather features after scenario overrides.
        row.loc[:, "rainfall_sum_2w"] = row["rainfall_mm"] + row["rainfall_lag_1"]
        row.loc[:, "rainfall_sum_4w"] = (
            row["rainfall_mm"] + row["rainfall_lag_1"]
            + row["rainfall_lag_2"] + row["rainfall_lag_3"]
        )

    return row[FEATURE_COLUMNS], pd.Timestamp(row["date"].iloc[0])
