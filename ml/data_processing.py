from __future__ import annotations

from pathlib import Path
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

def load_dataset(path: str | Path) -> pd.DataFrame:
    """Read and validate the DengueShield Excel/CSV dataset."""
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
    if df[["city", "ward_id"]].eq("").any().any():
        raise ValueError("Dataset contains blank city or ward_id values")
    if df.duplicated(["date", "ward_id"]).any():
        raise ValueError("Dataset contains duplicate date + ward_id records")
    return df.sort_values(["ward_id", "date"]).reset_index(drop=True)

def dataset_summary(df: pd.DataFrame) -> dict:
    """Return a compact dataset audit summary."""
    return {
        "rows": int(len(df)), "columns": int(len(df.columns)),
        "wards": int(df["ward_id"].nunique()), "cities": int(df["city"].nunique()),
        "date_start": str(df["date"].min().date()),
        "date_end": str(df["date"].max().date()),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_ward_dates": int(df.duplicated(["date", "ward_id"]).sum()),
    }
