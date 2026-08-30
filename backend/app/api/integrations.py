"""FHIR export, ABDM link, HIS push endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.fhir import AbdmService, FhirService, HisService
from app.models import AbdmLink, IntakeSession, User
from app.schemas import FhirExportRequest, FhirExportResponse
from app.security.deps import get_current_user, log_audit, require_clinician, require_patient
from app.utils import ok

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/fhir/export", response_model=FhirExportResponse)
def export_fhir(
    payload: FhirExportRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient_id = user.id if user.role == "PATIENT" else None
    if not patient_id:
        raise HTTPException(status_code=400, detail="Patient context required")
    svc = FhirService("mock")
    resources = svc.export_for_patient(db, patient_id)
    log_audit(db, actor=user, action="FHIR_EXPORTED", resource_type="fhir_bundle",
              resource_id=patient_id, request=request,
              detail=f"{{\"count\": {len(resources)}}}")
    return FhirExportResponse(exported=len(resources), resources=resources)


class AbhaLinkRequest(BaseModel):
    abha_id: str


@router.post("/abdm/link")
def abdm_link(
    payload: AbhaLinkRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_patient),
):
    svc = AbdmService("mock")
    link = svc.link_abha(db, user, payload.abha_id)
    user.abha_id = payload.abha_id
    db.commit()
    log_audit(db, actor=user, action="ABDM_LINKED", resource_type="abdm_link",
              resource_id=link.id, request=request, detail=f"abha={payload.abha_id}")
    return ok({"abha_id": link.abha_id, "status": link.status, "message": "Demo link created - no external data transmitted."})


@router.post("/his/push/{session_id}")
def his_push(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_clinician),
):
    s = db.get(IntakeSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Case not found")
    svc = HisService("mock")
    result = svc.push_encounter(db, s)
    log_audit(db, actor=user, action="HIS_PUSH", resource_type="encounter",
              resource_id=session_id, request=request, detail=str(result))
    return ok(result)
