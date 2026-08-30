"""Speech-to-text API (used by the patient kiosk for voice answers)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.speech import get_speech_provider, get_tts_provider
from app.security.deps import require_patient
from app.utils import ok

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(default="en"),
    db: Session = Depends(get_db),
    user=Depends(require_patient),
):
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Audio file required")
    content = await audio.read()
    provider = get_speech_provider()
    result = provider.transcribe(audio_bytes=content, mime=audio.content_type, language=language)
    return ok(result)


@router.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    language: str = Form(default="en"),
    db: Session = Depends(get_db),
    user=Depends(require_patient),
):
    provider = get_tts_provider()
    audio_bytes = provider.synthesize(text=text, language=language)

    from fastapi.responses import Response
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "attachment; filename=guidance.mp3"}
    )
