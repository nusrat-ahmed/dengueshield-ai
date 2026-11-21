from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS, feature_row_for_prediction, load_dataset
from ..config import DATASET_PATH, MODEL_DIR


class DenguePredictor:
    def __init__(self):
        self.data = load_dataset(DATASET_PATH)
        self.artifacts = {
            2: joblib.load(MODEL_DIR / "dengue_2week.joblib"),
            4: joblib.load(MODEL_DIR / "dengue_4week.joblib"),
        }
        self.latest_date = pd.Timestamp(self.data["date"].max())
        self.metrics = json.loads((MODEL_DIR / "training_metrics.json").read_text(encoding="utf-8"))
        self.city_wards = {
            city: sorted(group["ward_id"].unique().tolist())
            for city, group in self.data.groupby("city")
        }
        reference = self.data[self.data["date"] < pd.Timestamp("2024-01-01")]
        self._percentiles = {
            "rainfall_sum_4w": self._engineered_percentile("rainfall_sum_4w", 0.75),
            "water_logging_risk_index": float(reference["water_logging_risk_index"].quantile(0.75)),
            "population_density_sqkm": float(reference["population_density_sqkm"].quantile(0.75)),
            "sanitation_score_low": float(reference["sanitation_score"].quantile(0.25)),
            "relative_humidity_pct": float(reference["relative_humidity_pct"].quantile(0.75)),
            "dengue_cases_mean_4w": self._engineered_percentile("dengue_cases_mean_4w", 0.75),
        }

    def _engineered_percentile(self, column: str, q: float) -> float:
        from ml.features import add_features
        frame = add_features(self.data, include_targets=False)
        training_period = frame[frame["date"] < pd.Timestamp("2024-01-01")]
        return float(training_period[column].dropna().quantile(q))

    def _risk_level(self, predicted: float, thresholds: dict) -> str:
        if predicted <= thresholds["low_max"]:
            return "LOW"
        if predicted <= thresholds["medium_max"]:
            return "MEDIUM"
        if predicted <= thresholds["high_max"]:
            return "HIGH"
        return "CRITICAL"

    def _drivers(self, row: pd.DataFrame) -> list[dict]:
        values = row.iloc[0]
        checks = [
            ("Recent rainfall", float(values["rainfall_sum_4w"]) >= self._percentiles["rainfall_sum_4w"],
             "Rainfall accumulated over the recent four-week window is elevated."),
            ("Waterlogging vulnerability", float(values["water_logging_risk_index"]) >= self._percentiles["water_logging_risk_index"],
             "This ward has a relatively high waterlogging risk index."),
            ("Population density", float(values["population_density_sqkm"]) >= self._percentiles["population_density_sqkm"],
             "Higher population density can increase local transmission vulnerability."),
            ("Sanitation vulnerability", float(values["sanitation_score"]) <= self._percentiles["sanitation_score_low"],
             "The sanitation score is relatively low compared with the dataset."),
            ("Relative humidity", float(values["relative_humidity_pct"]) >= self._percentiles["relative_humidity_pct"],
             "Relative humidity is elevated compared with the dataset."),
            ("Recent dengue activity", float(values["dengue_cases_mean_4w"]) >= self._percentiles["dengue_cases_mean_4w"],
             "Recent reported dengue activity is elevated."),
        ]
        active = [{"driver": name, "status": "elevated", "explanation": explanation}
                  for name, passed, explanation in checks if passed]
        if not active:
            active.append({"driver": "No dominant elevated driver", "status": "neutral",
                           "explanation": "No selected input exceeded the dataset-based driver thresholds."})
        return active[:5]

    def predict(self, city: str, ward_id: str, horizon_weeks: int,
                as_of_date: str | None = None, weather_override: dict | None = None) -> dict:
        if city not in self.city_wards or ward_id not in self.city_wards[city]:
            raise ValueError("The selected ward does not belong to the selected city")
        row, reference_date = feature_row_for_prediction(
            self.data, ward_id, as_of_date=as_of_date, weather_override=weather_override
        )
        artifact = self.artifacts[horizon_weeks]
        raw_prediction = float(artifact["model"].predict(row[FEATURE_COLUMNS])[0])
        predicted = max(0.0, raw_prediction)
        thresholds = artifact["risk_thresholds"]
        forecast_date = reference_date + pd.Timedelta(weeks=horizon_weeks)
        record = {
            "city": city,
            "ward_id": ward_id,
            "horizon_weeks": horizon_weeks,
            "reference_date": reference_date.date().isoformat(),
            "forecast_target_date": forecast_date.date().isoformat(),
            "predicted_cases": round(predicted, 6),
            "risk_level": self._risk_level(predicted, thresholds),
            "risk_thresholds": thresholds,
            "weather_inputs": {
                "avg_temp_c": round(float(row.iloc[0]["avg_temp_c"]), 2),
                "rainfall_mm": round(float(row.iloc[0]["rainfall_mm"]), 2),
                "relative_humidity_pct": round(float(row.iloc[0]["relative_humidity_pct"]), 2),
                "rainfall_sum_2w": round(float(row.iloc[0]["rainfall_sum_2w"]), 2),
                "rainfall_sum_4w": round(float(row.iloc[0]["rainfall_sum_4w"]), 2),
            },
            "risk_drivers": self._drivers(row),
            "model_name": artifact["metrics"]["selected_model"],
            "data_note": (
                f"Historical dataset ends on {self.latest_date.date()}. This is a model-based "
                "scenario forecast anchored to the selected historical reference week, not a live 2026 forecast. "
                "Use verified current weather and case data before operational decisions."
            ),
        }
        return record

    def metadata(self) -> dict:
        return {
            "dataset": {
                "rows": self.metrics["dataset_rows"],
                "wards": self.metrics["wards"],
                "cities": self.metrics["cities"],
                "start_date": self.metrics["date_start"],
                "end_date": self.metrics["date_end"],
                "missing_values": self.metrics["missing_values"],
                "duplicate_ward_dates": self.metrics["duplicate_ward_dates"],
            },
            "models": self.metrics["models"],
            "latest_date": self.latest_date.date().isoformat(),
        }

    def ward_options(self, city: str | None = None) -> list[dict]:
        frame = self.data[["city", "ward_id"]].drop_duplicates().sort_values(["city", "ward_id"])
        if city:
            frame = frame[frame["city"] == city]
        return frame.to_dict(orient="records")

    def dates_for_ward(self, ward_id: str) -> list[str]:
        dates = self.data.loc[self.data.ward_id == ward_id, "date"].sort_values()
        return [d.date().isoformat() for d in dates]

    def feature_importance(self, horizon: int) -> list[dict]:
        artifact = self.artifacts[horizon]
        model = artifact["model"].named_steps["model"]
        preprocessor = artifact["model"].named_steps["preprocess"]
        names = preprocessor.get_feature_names_out()
        importances = model.feature_importances_
        pairs = sorted(zip(names, importances), key=lambda x: x[1], reverse=True)[:12]
        return [{"feature": str(name).replace("num__", "").replace("cat__", ""),
                 "importance": round(float(value), 5)} for name, value in pairs]


predictor = None

def get_predictor() -> DenguePredictor:
    global predictor
    if predictor is None:
        predictor = DenguePredictor()
    return predictor
