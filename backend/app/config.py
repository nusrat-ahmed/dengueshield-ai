from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATASET_PATH = Path(os.getenv("DATASET_PATH", str(ROOT / "data/raw/dengue_dataset.xlsx")))
if not DATASET_PATH.is_absolute():
    DATASET_PATH = ROOT / DATASET_PATH
MODEL_DIR = Path(os.getenv("MODEL_DIR", str(ROOT / "models")))
if not MODEL_DIR.is_absolute():
    MODEL_DIR = ROOT / MODEL_DIR
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "data/dengueshield.sqlite3")))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = ROOT / DATABASE_PATH
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_TABLE = os.getenv("SUPABASE_TABLE", "prediction_history").strip()
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if x.strip()]
