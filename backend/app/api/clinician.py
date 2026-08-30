"""Clinician dashboard, case review, verification, notes, timeline."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    AbdmLink,
    ClinicalSummary,
    DoctorNote,
    IntakeSession,
    MedicalDocument,
    PatientProfile,
    RedFlag,
    TimelineEvent,
    User,
    VerificationRecord,
)
from app.schemas import (
    CaseListItem,
    DashboardCounts,
    IntegrationStatus,
    NoteRequest,
    SummaryOut,
    VerifyRequest,
)
from app.security.deps import get_current_user, log_audit, require_clinician
from app.utils import ok

router = APIRouter(prefix="/clinician", tags=["clinician"])


def _age(dob: Optional[str]) -> Optional[int]:
    if not dob:
        return None
    try:
        d = datetime.strptime(dob, "%Y-%m-%d")
        return max(0, (datetime.utcnow() - d).days // 365)
    except Exception:
        return None


@router.get("/dashboard", response_model=DashboardCounts)
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_clinician)):
    base = db.query(IntakeSession)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    new_cases = base.filter(IntakeSession.status == "REVIEW_REQUIRED").count()
    pending_review = base.filter(IntakeSession.status == "REVIEW_REQUIRED").count()
    priority_cases = base.filter(IntakeSession.priority == "PRIORITY").count()
    completed_cases = base.filter(IntakeSession.status == "COMPLETED").count()
    today_queue = base.filter(func.date(IntakeSession.started_at) == today).count()
    return DashboardCounts(
        new_cases=new_cases,
        pending_review=pending_review,
        priority_cases=priority_cases,
        completed_cases=completed_cases,
        today_queue=today_queue,
    )


@router.get("/queue")
def queue(
    priority_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_clinician),
):
    q = db.query(IntakeSession)
    if priority_only:
        q = q.filter(IntakeSession.priority == "PRIORITY")
    sessions = q.order_by(IntakeSession.submitted_at.desc().nullslast(), IntakeSession.started_at.desc()).limit(200).all()
    out: list[dict] = []
    for s in sessions:
        patient = db.get(User, s.patient_id)
        profile = db.query(PatientProfile).filter_by(user_id=s.patient_id).first()
        out.append({
            "session_id": s.id,
            "patient_id": s.patient_id,
            "patient_name": patient.full_name if patient else "Unknown",
            "patient_age": _age(profile.date_of_birth) if profile else None,
            "patient_gender": profile.gender if profile else None,
            "chief_complaint": s.chief_complaint,
            "priority": s.priority,
            "status": s.status,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
            "red_flag_count": db.query(RedFlag).filter_by(session_id=s.id).count(),
        })
    return ok(out)


@router.get("/case/{session_id}")
def get_case(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_clinician),
):
    s = db.get(IntakeSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Case not found")
    patient = db.get(User, s.patient_id)
    profile = db.query(PatientProfile).filter_by(user_id=s.patient_id).first()
    summary = db.query(ClinicalSummary).filter_by(session_id=s.id).one_or_none()
    flags = db.query(RedFlag).filter_by(session_id=s.id).all()
    docs = db.query(MedicalDocument).filter_by(session_id=s.id).all()
    notes = db.query(DoctorNote).filter_by(session_id=s.id).order_by(DoctorNote.created_at.desc()).all()
    abdm = db.query(AbdmLink).filter_by(patient_id=s.patient_id).first()

    return ok({
        "session": {
            "id": s.id,
            "patient_id": s.patient_id,
            "language": s.language,
            "mode": s.mode,
            "status": s.status,
            "chief_complaint": s.chief_complaint,
            "priority": s.priority,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        },
        "patient": {
            "id": patient.id,
            "full_name": patient.full_name,
            "email": patient.email,
            "phone": patient.phone,
            "abha_id": patient.abha_id,
            "preferred_language": patient.preferred_language,
            "date_of_birth": profile.date_of_birth if profile else None,
            "gender": profile.gender if profile else None,
            "blood_group": profile.blood_group if profile else None,
        },
        "abdm": {"abha_id": abdm.abha_id, "status": abdm.status} if abdm else None,
        "answers": [
            {
                "id": a.id, "question_code": a.question_code, "answer_text": a.answer_text,
                "answer_value": json.loads(a.answer_value) if a.answer_value else None,
                "source": a.source, "created_at": a.created_at.isoformat(),
            } for a in s.answers
        ],
        "summary": {
            "prose": summary.prose if summary else "",
            "structured": json.loads(summary.structured_json) if summary else {},
            "is_ai_generated": summary.is_ai_generated if summary else False,
            "ai_provider": summary.ai_provider if summary else "",
            "verification_status": summary.verification_status if summary else "DRAFT",
        } if summary else None,
        "red_flags": [
            {"id": f.id, "code": f.code, "message": f.message, "severity": f.severity,
             "triggered_by": json.loads(f.triggered_by) if f.triggered_by else []}
            for f in flags
        ],
        "documents": [
            {
                "id": d.id, "filename": d.filename, "document_type": d.document_type,
                "document_date": d.document_date, "ocr_text": d.ocr_text,
                "extractions": [
                    {"id": e.id, "entity_type": e.entity_type, "payload": json.loads(e.payload_json),
                     "verification_status": e.verification_status}
                    for e in d.extractions
                ],
            } for d in docs
        ],
        "notes": [
            {"id": n.id, "author_id": n.author_id, "note_type": n.note_type, "content": n.content,
             "is_private": n.is_private, "created_at": n.created_at.isoformat()}
            for n in notes
        ],
    })


@router.post("/case/{session_id}/status")
def update_status(
    session_id: str,
    status: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_clinician),
):
    s = db.get(IntakeSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Case not found")
    if status not in ("WAITING", "IN_PROGRESS", "REVIEW_REQUIRED", "REVIEWED", "COMPLETED", "PRIORITY"):
        raise HTTPException(status_code=400, detail="Invalid status")
    s.status = status
    if status == "IN_PROGRESS" and not s.assigned_clinician_id:
        s.assigned_clinician_id = user.id
    db.commit()
    log_audit(db, actor=user, action="CASE_STATUS_CHANGED", resource_type="intake_session", resource_id=session_id,
              request=request, detail=json.dumps({"status": status}))
    return ok(message=f"Case moved to {status}")


@router.post("/case/{session_id}/note", status_code=201)
def add_note(
    session_id: str,
    payload: NoteRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_clinician),
):
    s = db.get(IntakeSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Case not found")
    note = DoctorNote(
        session_id=session_id, author_id=user.id,
        note_type=payload.note_type, content=payload.content, is_private=payload.is_private,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    log_audit(db, actor=user, action="NOTE_ADDED", resource_type="doctor_note", resource_id=note.id, request=request)
    return ok({"id": note.id, "created_at": note.created_at.isoformat()})


@router.post("/verify", status_code=201)
def verify_field(
    payload: VerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_clinician),
):
    rec = VerificationRecord(
        target_type=payload.target_type,
        target_id=payload.target_id,
        status=payload.status,
        original_value=None,
        modified_value=payload.modified_value,
        actor_id=user.id,
    )
    db.add(rec)
    db.commit()
    log_audit(db, actor=user, action=f"FIELD_{payload.status}", resource_type=payload.target_type,
              resource_id=payload.target_id, request=request)
    return ok(message=f"Field marked {payload.status}")


@router.get("/timeline/{patient_id}")
def timeline(
    patient_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "PATIENT" and user.id != patient_id:
        raise HTTPException(status_code=403, detail="Not your timeline")
    rows = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.patient_id == patient_id)
        .order_by(TimelineEvent.event_date.desc().nullslast(), TimelineEvent.created_at.desc())
        .all()
    )
    return ok([
        {
            "id": r.id, "event_type": r.event_type, "event_date": r.event_date,
            "title": r.title, "detail": r.detail, "source": r.source,
            "ref_id": r.ref_id, "created_at": r.created_at.isoformat(),
        } for r in rows
    ])


@router.get("/integrations/status", response_model=IntegrationStatus)
def integrations_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_clinician),
):
    from app.fhir import AbdmService, FhirService, HisService
    return IntegrationStatus(
        abdm=AbdmService("mock").status(),
        fhir=FhirService("mock").status(),
        his=HisService("mock").status(),
        consent={"status": "granted", "message": "Patient consents logged in audit trail."},
    )
