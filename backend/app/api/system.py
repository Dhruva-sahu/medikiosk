"""Health, system info, and one-time seed endpoint."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.utils import ok

logger = logging.getLogger(__name__)
router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return ok({
        "service": settings.app_name,
        "environment": settings.app_env,
        "ai_mode": settings.ai_mode,
        "ocr_provider": settings.ocr_provider,
        "speech_provider": settings.speech_provider,
        "database": "ok" if db_ok else "down",
        "now": datetime.utcnow().isoformat() + "Z",
    })


@router.post("/seed")
def seed_database():
    """Populate demo users, cases, and documents.

    Idempotent — safe to call multiple times. Skips users that already
    exist and only creates missing demo data.
    """
    try:
        from app.seed import run as seed_run
        seed_run()
        return ok("Demo data seeded successfully")
    except Exception as exc:
        logger.exception("Seed failed: %r", exc)
        return ok({"error": str(exc)})
