"""AI service that ties the question engine, provider, and DB together.

This version uses the AI-driven conversation engine instead of the
predefined question catalogue.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai import (
    detect_red_flags_from_conversation,
    structured_from_conversation,
    MAX_QUESTIONS,
)
from app.ai.provider import get_ai_provider
from app.models import (
    ClinicalSummary,
    DoctorNote,
    IntakeAnswer,
    IntakeSession,
    MedicalDocument,
    RedFlag,
    TimelineEvent,
)


def start_session(db: Session, *, patient_id: str, language: str, mode: str, consent_id: Optional[str]) -> IntakeSession:
    s = IntakeSession(
        patient_id=patient_id,
        language=language,
        mode=mode.upper(),
        consent_id=consent_id,
        status="IN_PROGRESS",
        question_count=0,
        conversation_history="[]",
        collected_data="{}",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _auto_extract_clinical_data(collected: dict, question_code: str, answer_text: str) -> None:
    """Extract structured clinical data from a patient answer based on the question category."""
    a = answer_text.strip()
    if not a:
        return
    code = (question_code or "").lower()

    _map = {
        "chief_complaint": "chief_complaint",
        "duration": "duration",
        "onset": "onset",
        "location": "location",
        "character": "character",
        "associated_symptoms": "associated_symptoms",
        "aggravating": "aggravating_factors",
        "relieving": "relieving_factors",
        "timing": "timing",
        "radiation": "radiation",
        "past_medical": "past_medical_history",
        "past_surgical": "past_surgical_history",
        "medications": "medications",
        "drug_history": "drug_history",
        "allergies": "allergies",
        "family_history": "family_history",
        "personal_history": "personal_history",
        "review_of_systems": "review_of_systems",
    }

    key = _map.get(code)
    if key and key not in collected:
        collected[key] = a

    # Special handling for severity — try to extract a number
    if code == "severity":
        import re
        nums = re.findall(r"\d+", a.lower())
        if nums:
            collected["severity"] = nums[0]

    # Smoking/alcohol from personal_history
    if code == "personal_history":
        al = a.lower()
        if "smok" in al:
            collected["smoking"] = "yes" if "no" not in al.split("smok")[0][-5:] else "no"
        if "alcohol" in al or "drink" in al:
            collected["alcohol"] = "yes" if "no" not in al.split("alcohol")[0][-5:] else "no"


def answer_session(
    db: Session,
    *,
    session: IntakeSession,
    question_code: str,
    answer_text: Optional[str],
    answer_value: Optional[Any],
    source: str = "PATIENT_TOUCH",
    question_category: Optional[str] = None,
    clinical_data_extracted: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record an answer and update conversation history + collected data."""
    if session.status not in ("IN_PROGRESS", "WAITING"):
        pass

    # Record the answer in the answers table
    ans = IntakeAnswer(
        session_id=session.id,
        question_code=question_code,
        answer_text=(answer_text or "").strip() if isinstance(answer_text, str) else None,
        answer_value=json.dumps(answer_value) if answer_value is not None else None,
        source=source,
    )
    db.add(ans)

    # Update chief complaint from first answer
    if question_code in ("chief_complaint", "CHIEF_COMPLAINT") and answer_text and not session.chief_complaint:
        session.chief_complaint = answer_text.strip()

    # Update conversation history
    history = json.loads(session.conversation_history or "[]")
    if answer_text:
        history.append({"role": "patient", "content": answer_text.strip()})
    session.conversation_history = json.dumps(history)

    # Update collected data with AI-extracted clinical data
    collected = json.loads(session.collected_data or "{}")
    if clinical_data_extracted:
        collected.update(clinical_data_extracted)
    else:
        # Auto-extract clinical data from the answer based on question category
        _auto_extract_clinical_data(collected, question_code, answer_text or "")
    session.collected_data = json.dumps(collected)

    # Increment question count
    session.question_count = (session.question_count or 0) + 1

    db.commit()
    db.refresh(session)
    return {"answer_id": ans.id, "question_count": session.question_count}


def get_next_question(db: Session, session: IntakeSession) -> Optional[Dict[str, Any]]:
    """Use the AI provider to generate the next question based on conversation context."""
    provider = get_ai_provider()

    history = json.loads(session.conversation_history or "[]")
    collected = json.loads(session.collected_data or "{}")
    q_count = session.question_count or 0

    # If we've hit the max, signal completion
    if q_count >= MAX_QUESTIONS:
        return None

    result = provider.generate_question(
        conversation_history=history,
        collected_data=collected,
        question_count=q_count,
        chief_complaint=session.chief_complaint,
        mode=session.mode,
        language=session.language,
    )

    if result.get("should_finish") or not result.get("question"):
        return None

    # Build progress info
    progress_pct = int(q_count * 100 / MAX_QUESTIONS) if MAX_QUESTIONS else 0

    return {
        "code": result.get("category", "other"),
        "domain": result.get("category", "OTHER").upper(),
        "prompt": result["question"],
        "answer_type": "text",  # All AI questions are free-text
        "options": None,
        "required": True,
        "progress": progress_pct,
        "total": MAX_QUESTIONS,
        "question_count": q_count,
        # Store metadata for the answer submission
        "_ai_metadata": {
            "category": result.get("category"),
            "reason": result.get("reason"),
            "clinical_data": result.get("clinical_data", {}),
            "red_flag": result.get("red_flag", False),
            "red_flag_message": result.get("red_flag_message"),
        },
    }


def session_state(db: Session, session: IntakeSession) -> Dict[str, Any]:
    history = json.loads(session.conversation_history or "[]")
    collected = json.loads(session.collected_data or "{}")
    q_count = session.question_count or 0
    progress_pct = int(q_count * 100 / MAX_QUESTIONS) if MAX_QUESTIONS else 0

    nq = get_next_question(db, session) if session.status == "IN_PROGRESS" else None
    # Strip internal AI metadata
    if nq and "_ai_metadata" in nq:
        del nq["_ai_metadata"]

    return {
        "session_id": session.id,
        "status": session.status,
        "language": session.language,
        "mode": session.mode,
        "chief_complaint": session.chief_complaint,
        "priority": session.priority,
        "progress": progress_pct,
        "answered_count": q_count,
        "total_questions": MAX_QUESTIONS,
        "next_question": nq,
        "conversation_history": history,
        "collected_data": collected,
        "answered": [
            {
                "id": a.id,
                "question_code": a.question_code,
                "answer_text": a.answer_text,
                "source": a.source,
                "created_at": a.created_at.isoformat(),
            } for a in session.answers
        ],
    }


def submit_session(db: Session, session: IntakeSession, ayush: Optional[dict] = None) -> Dict[str, Any]:
    """Finalise the session: build structured data, red-flags, summary, timeline."""
    session.status = "REVIEW_REQUIRED"
    session.submitted_at = datetime.utcnow()

    history = json.loads(session.conversation_history or "[]")
    collected = json.loads(session.collected_data or "{}")

    structured = structured_from_conversation(history, collected, session.chief_complaint)

    if ayush:
        structured["ayush"].update({k: v for k, v in ayush.items() if v})

    # Documents attached to the session
    documents = db.query(MedicalDocument).filter(MedicalDocument.session_id == session.id).all()
    docs_summary = [
        {
            "id": d.id,
            "filename": d.filename,
            "type": d.document_type,
            "date": d.document_date,
            "extractions": [
                {"entity_type": e.entity_type, "payload": json.loads(e.payload_json)}
                for e in d.extractions
            ],
        }
        for d in documents
    ]

    # Red flags â€” use the AI conversation-based detection
    flags = detect_red_flags_from_conversation(history, collected)

    # Persist red flags
    db.query(RedFlag).filter(RedFlag.session_id == session.id).delete()
    for f in flags:
        db.add(RedFlag(
            session_id=session.id,
            code=f["code"],
            message=f["message"],
            severity=f.get("severity", "HIGH"),
            triggered_by=json.dumps(f.get("triggered_by", [])),
        ))
    if flags:
        session.priority = "PRIORITY"

    # AI summary
    provider = get_ai_provider()
    result = provider.summarise(structured=structured, documents=docs_summary, red_flags=flags)
    prose = result["summary_text"]

    # Upsert clinical summary
    existing = db.query(ClinicalSummary).filter(ClinicalSummary.session_id == session.id).one_or_none()
    if existing:
        existing.structured_json = json.dumps(result.get("structured") or structured)
        existing.prose = prose
        existing.is_ai_generated = bool(result.get("is_ai_generated"))
        existing.ai_provider = result.get("provider", provider.name)
    else:
        db.add(ClinicalSummary(
            session_id=session.id,
            patient_id=session.patient_id,
            structured_json=json.dumps(result.get("structured") or structured),
            prose=prose,
            is_ai_generated=bool(result.get("is_ai_generated")),
            ai_provider=result.get("provider", provider.name),
            verification_status="DRAFT",
        ))

    # Timeline events for the patient
    db.add(TimelineEvent(
        patient_id=session.patient_id,
        event_type="INTAKE",
        event_date=datetime.utcnow().strftime("%Y-%m-%d"),
        title="Clinical intake completed",
        detail=session.chief_complaint or "Patient submitted history",
        ref_id=session.id,
        source="MEDIKIOSK",
    ))
    for d in documents:
        db.add(TimelineEvent(
            patient_id=session.patient_id,
            event_type="DOCUMENT",
            event_date=d.document_date,
            title=f"Document: {d.filename}",
            detail=d.document_type or "Other",
            ref_id=d.id,
            source="OCR_EXTRACTED",
        ))

    db.commit()

    return {
        "session_id": session.id,
        "status": session.status,
        "priority": session.priority,
        "prose": prose,
        "structured": result.get("structured") or structured,
        "red_flags": flags,
        "is_ai_generated": result.get("is_ai_generated", False),
        "ai_provider": result.get("provider", provider.name),
    }
