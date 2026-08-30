"""Health and system info endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.utils import ok

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
