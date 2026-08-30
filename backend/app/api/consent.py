"""Consent capture and management API."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Consent, User
from app.schemas import ConsentRequest, ConsentOut
from app.security.deps import get_current_user, log_audit, require_patient
from app.utils import ok

router = APIRouter(prefix="/consent", tags=["consent"])


@router.post("", response_model=ConsentOut, status_code=201)
def grant_consent(
    payload: ConsentRequest,
    request: Request,
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    consent = Consent(
        patient_id=user.id,
        scope=json.dumps(payload.scope),
        purpose=payload.purpose or "Clinical intake and sharing with treating doctor",
        status="GRANTED",
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    log_audit(db, actor=user, action="CONSENT_GRANTED",
              resource_type="consent", resource_id=consent.id, request=request)
    return ConsentOut(
        id=consent.id,
        consent_version=consent.consent_version,
        scope=json.loads(consent.scope),
        status=consent.status,
        purpose=consent.purpose,
        granted_at=consent.granted_at,
    )


@router.get("/mine")
def list_my_consents(
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    rows = db.query(Consent).filter(Consent.patient_id == user.id).order_by(Consent.granted_at.desc()).all()
    return ok([
        {
            "id": r.id,
            "consent_version": r.consent_version,
            "scope": json.loads(r.scope) if r.scope else [],
            "status": r.status,
            "purpose": r.purpose,
            "granted_at": r.granted_at.isoformat(),
        } for r in rows
    ])


@router.post("/{consent_id}/revoke")
def revoke_consent(
    consent_id: str,
    request: Request,
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    c = db.query(Consent).filter(Consent.id == consent_id, Consent.patient_id == user.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Consent not found")
    from datetime import datetime
    c.status = "REVOKED"
    c.revoked_at = datetime.utcnow()
    db.commit()
    log_audit(db, actor=user, action="CONSENT_REVOKED",
              resource_type="consent", resource_id=consent_id, request=request)
    return ok(message="Consent revoked")
