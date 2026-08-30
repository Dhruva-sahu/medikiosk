"""Patient intake API."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.ai.service import answer_session, get_next_question, session_state, start_session, submit_session
from app.db import get_db
from app.models import Consent, IntakeSession, User
from app.schemas import (
    AnswerRequest,
    IntakeSessionOut,
    IntakeStartRequest,
    IntakeSubmitRequest,
    QuestionOut,
    SummaryOut,
)
from app.security.deps import get_current_user, log_audit, require_patient
from app.utils import ok

router = APIRouter(prefix="/intake", tags=["intake"])


def _ensure_latest_consent(db: Session, user: User) -> Consent:
    c = db.query(Consent).filter(Consent.patient_id == user.id, Consent.status == "GRANTED").order_by(Consent.granted_at.desc()).first()
    if not c:
        # Auto-grant a default consent to keep the demo flowing
        c = Consent(
            patient_id=user.id,
            scope='["history","documents","ai_processing","summary","his_share","abdm_share"]',
            purpose="Default clinical intake consent",
            status="GRANTED",
        )
        db.add(c)
        db.commit()
        db.refresh(c)
    return c


@router.post("/start", response_model=IntakeSessionOut, status_code=201)
def start(
    payload: IntakeStartRequest,
    request: Request,
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    consent = _ensure_latest_consent(db, user)
    s = start_session(db, patient_id=user.id, language=payload.language, mode=payload.mode, consent_id=consent.id)
    log_audit(db, actor=user, action="INTAKE_STARTED", resource_type="intake_session", resource_id=s.id, request=request)
    return s


@router.get("/sessions")
def list_my_sessions(
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    rows = db.query(IntakeSession).filter(IntakeSession.patient_id == user.id).order_by(IntakeSession.started_at.desc()).all()
    return ok([_session_to_dict(r) for r in rows])


def _session_to_dict(s: IntakeSession) -> dict:
    return {
        "id": s.id,
        "patient_id": s.patient_id,
        "language": s.language,
        "mode": s.mode,
        "status": s.status,
        "chief_complaint": s.chief_complaint,
        "priority": s.priority,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
    }


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.get(IntakeSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Intake session not found")
    if user.role == "PATIENT" and s.patient_id != user.id:
        raise HTTPException(status_code=403, detail="Not your session")
    state = session_state(db, s)
    state["session"] = _session_to_dict(s)
    return state


@router.get("/sessions/{session_id}/next-question")
def next_question(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.get(IntakeSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Intake session not found")
    if user.role == "PATIENT" and s.patient_id != user.id:
        raise HTTPException(status_code=403, detail="Not your session")
    # Idempotent: if the last conversation entry is an unanswered assistant
    # question, return it directly instead of generating a new one.
    history = json.loads(s.conversation_history or "[]")
    if history and history[-1].get("role") == "assistant":
        pending = history[-1]
        nq = {
            "code": pending.get("category", "other"),
            "domain": (pending.get("category", "other") or "other").upper(),
            "prompt": pending["content"],
            "answer_type": "text",
            "options": None,
            "required": True,
            "progress": int((s.question_count or 0) * 100 / 17),
            "total": 17,
            "question_count": s.question_count or 0,
        }
        return ok({"next_question": nq, "is_complete": False})

    nq = get_next_question(db, s)
    # Record the assistant's question in conversation history so the AI
    # sees its own questions for context on the next turn.
    if nq and nq.get("prompt"):
        history.append({
            "role": "assistant",
            "content": nq["prompt"],
            "category": nq.get("code", "other"),
        })
        s.conversation_history = json.dumps(history)
        db.commit()
    # Strip internal AI metadata from the response
    if nq and "_ai_metadata" in nq:
        del nq["_ai_metadata"]
    return ok({"next_question": nq, "is_complete": nq is None})


@router.post("/sessions/{session_id}/answer", status_code=201)
def submit_answer(
    session_id: str,
    payload: AnswerRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.get(IntakeSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Intake session not found")
    if user.role == "PATIENT" and s.patient_id != user.id:
        raise HTTPException(status_code=403, detail="Not your session")
    answer_session(
        db, session=s,
        question_code=payload.question_code,
        answer_text=payload.answer_text,
        answer_value=payload.answer_value,
        source=payload.source,
        question_category=payload.question_category,
        clinical_data_extracted=payload.clinical_data_extracted,
    )
    log_audit(db, actor=user, action="ANSWER_RECORDED",
              resource_type="intake_answer", resource_id=payload.question_code, request=request)
    return ok({"status": "recorded"})


@router.post("/sessions/{session_id}/submit", response_model=SummaryOut)
def submit(
    session_id: str,
    payload: IntakeSubmitRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.get(IntakeSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Intake session not found")
    if user.role == "PATIENT" and s.patient_id != user.id:
        raise HTTPException(status_code=403, detail="Not your session")
    if payload.final_chief_complaint:
        s.chief_complaint = payload.final_chief_complaint
    result = submit_session(db, s, ayush=payload.ayush)
    log_audit(db, actor=user, action="CASE_SUBMITTED",
              resource_type="intake_session", resource_id=session_id, request=request,
              detail=json.dumps({"red_flags": len(result["red_flags"]), "priority": result["priority"]}))
    return SummaryOut(
        session_id=result["session_id"],
        prose=result["prose"],
        structured=result["structured"],
        red_flags=result["red_flags"],
        is_ai_generated=result["is_ai_generated"],
        ai_provider=result["ai_provider"],
        verification_status="DRAFT",
    )
