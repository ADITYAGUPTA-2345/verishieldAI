"""Backend configuration. Provider credentials never enter extension code."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # Legacy local settings.
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "").strip()
MODEL_PATH = Path(os.getenv("VERISHIELD_MODEL_PATH", str(Path(__file__).resolve().parents[2] / "ml/artifacts/job_classifier.joblib")))
MAX_TEXT_CHARS = int(os.getenv("VERISHIELD_MAX_TEXT_CHARS", "50000"))
if not 1 <= MAX_TEXT_CHARS <= 200000:
    raise ValueError("VERISHIELD_MAX_TEXT_CHARS must be between 1 and 200000")
