from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

import httpx

from .config import DATABASE_PATH, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_TABLE


def _sqlite_save(record: dict) -> str:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    prediction_id = str(uuid.uuid4())
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS prediction_history (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, city TEXT NOT NULL,
            ward_id TEXT NOT NULL, horizon_weeks INTEGER NOT NULL,
            reference_date TEXT NOT NULL, forecast_target_date TEXT NOT NULL,
            predicted_cases REAL NOT NULL, risk_level TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )""")
        conn.execute("""INSERT INTO prediction_history
            (id, created_at, city, ward_id, horizon_weeks, reference_date,
             forecast_target_date, predicted_cases, risk_level, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (prediction_id, datetime.now(timezone.utc).isoformat(), record["city"],
             record["ward_id"], record["horizon_weeks"], record["reference_date"],
             record["forecast_target_date"], record["predicted_cases"],
             record["risk_level"], json.dumps(record)))
    return prediction_id


def save_prediction(record: dict) -> str:
    """Persist through Supabase when configured; otherwise use local SQLite."""
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        payload = {**record, "created_at": datetime.now(timezone.utc).isoformat()}
        try:
            response = httpx.post(
                f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_TABLE}",
                headers=headers, json=payload, timeout=8.0,
            )
            response.raise_for_status()
            rows = response.json()
            if rows and isinstance(rows, list):
                return str(rows[0].get("id", "supabase-saved"))
            return "supabase-saved"
        except Exception:
            # Local fallback keeps the prediction usable during provider outages.
            pass
    return _sqlite_save(record)


def recent_predictions(limit: int = 10) -> list[dict]:
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        headers = {"apikey": SUPABASE_SERVICE_ROLE_KEY,
                   "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"}
        try:
            response = httpx.get(
                f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_TABLE}",
                headers=headers, params={"select": "*", "order": "created_at.desc", "limit": str(limit)},
                timeout=5.0,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            pass
    if not DATABASE_PATH.exists():
        return []
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM prediction_history ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        except sqlite3.OperationalError:
            return []
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.pop("payload_json"))
        except Exception:
            pass
        result.append(item)
    return result
