
from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .schemas import PredictionRequest
from .services.predictor import get_predictor
from .storage import recent_predictions, save_prediction


app = FastAPI(
    title="DengueShield AI API",
    description="Ward-level dengue early-warning predictions using historical weather and vulnerability features.",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    try:
        engine = get_predictor()

        return {
            "status": "ok",
            "model_loaded": True,
            "dataset_end": engine.latest_date.date().isoformat(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Prediction engine unavailable: {exc}",
        )


@app.get("/meta")
def meta():
    try:
        return get_predictor().metadata()

    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/cities")
def cities():
    return {
        "cities": sorted(get_predictor().city_wards.keys())
    }


@app.get("/wards")
def wards(city: str | None = None):
    return {
        "wards": get_predictor().ward_options(city)
    }


@app.get("/dates/{ward_id}")
def dates(ward_id: str):
    values = get_predictor().dates_for_ward(ward_id)

    if not values:
        raise HTTPException(
            status_code=404,
            detail="Ward not found",
        )

    return {"dates": values}


@app.post("/predict")
def predict(payload: PredictionRequest):
    try:
        record = get_predictor().predict(
            city=payload.city,
            ward_id=payload.ward_id,
            horizon_weeks=payload.horizon_weeks,
            as_of_date=(
                payload.as_of_date.isoformat()
                if payload.as_of_date
                else None
            ),
            weather_override=(
                payload.weather_override.model_dump(exclude_none=True)
                if payload.weather_override
                else None
            ),
        )

        record["prediction_id"] = save_prediction(record)

        return record

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {exc}",
        )



@app.get("/metrics")
def metrics(horizon_weeks: int = Query(default=2)):
    try:
        if horizon_weeks not in (2, 4):
            raise HTTPException(
                status_code=422,
                detail="horizon_weeks must be 2 or 4"
            )

        engine = get_predictor()

        return {
            "horizon_weeks": horizon_weeks,
            "model": engine.artifacts[horizon_weeks]["metrics"],
            "feature_importance": engine.feature_importance(
                horizon_weeks
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )



@app.get("/history")
def history(
    limit: int = Query(default=10, ge=1, le=100)
):
    return {
        "items": recent_predictions(limit)
    }
