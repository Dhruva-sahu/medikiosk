"""Document upload, OCR and entity extraction API."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import (
    DocumentExtraction,
    IntakeSession,
    LabResult,
    MedicalDocument,
    MedicalHistoryItem,
    MedicationRecord,
    TimelineEvent,
    User,
)
from app.ocr import extract_medical_entities, get_ocr_provider
from app.security.deps import get_current_user, log_audit, require_patient
from app.schemas import DocumentOut, ExtractionOut
from app.utils import ok

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "application/pdf"}


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    session_id: str | None = None,
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    # Persist file
    ext = os.path.splitext(file.filename or "")[1].lower() or ".bin"
    doc_id = str(uuid.uuid4())
    safe = f"{doc_id}{ext}"
    storage = settings.upload_path / safe
    storage.write_bytes(content)

    # Run OCR
    ocr = get_ocr_provider()
    result = ocr.extract(filename=file.filename or safe, mime=file.content_type, content=content)

    # Run entity extraction on the OCR text
    entities = extract_medical_entities(result["text"])

    # Persist document
    document = MedicalDocument(
        id=doc_id,
        patient_id=user.id,
        session_id=session_id,
        filename=file.filename or safe,
        mime_type=file.content_type,
        storage_path=str(storage),
        document_type=result["document_type"],
        ocr_text=result["text"],
        ocr_confidence=result["confidence"],
        ocr_provider=result["provider"],
        document_date=entities.get("document_date"),
    )
    db.add(document)
    db.flush()

    # Persist extractions
    extraction_summary: List[dict] = []

    for med in entities["medications"]:
        ex_id = str(uuid.uuid4())
        payload = {"name": med["name"], "dose": med["dose"], "unit": med["unit"], "raw": med["raw"]}
        db.add(DocumentExtraction(
            id=ex_id, document_id=document.id, entity_type="MEDICATION", payload_json=json.dumps(payload),
        ))
        db.add(MedicationRecord(
            patient_id=user.id, name=med["name"], dose=f"{med['dose']} {med['unit']}".strip(),
            source="OCR_EXTRACTED", source_ref=document.id,
        ))
        extraction_summary.append({"id": ex_id, "entity_type": "MEDICATION", "payload": payload, "verification_status": "UNVERIFIED"})

    for lab in entities["lab_values"]:
        ex_id = str(uuid.uuid4())
        payload = {k: lab[k] for k in ["test_name", "value", "unit", "reference_range", "abnormal_flag"]}
        db.add(DocumentExtraction(
            id=ex_id, document_id=document.id, entity_type="LAB", payload_json=json.dumps(payload),
        ))
        db.add(LabResult(
            patient_id=user.id,
            test_name=lab["test_name"],
            value=lab["value"],
            unit=lab["unit"],
            reference_range=lab["reference_range"],
            abnormal_flag=lab["abnormal_flag"],
            test_date=document.document_date,
            source="OCR_EXTRACTED",
            source_ref=document.id,
        ))
        extraction_summary.append({"id": ex_id, "entity_type": "LAB", "payload": payload, "verification_status": "UNVERIFIED"})

    for diag in entities["diagnoses"]:
        ex_id = str(uuid.uuid4())
        payload = diag
        db.add(DocumentExtraction(
            id=ex_id, document_id=document.id, entity_type="DIAGNOSIS", payload_json=json.dumps(payload),
        ))
        db.add(MedicalHistoryItem(
            patient_id=user.id, category="PAST_MEDICAL", label=diag["label"], detail=diag["evidence"],
            source="OCR_EXTRACTED", source_ref=document.id,
        ))
        extraction_summary.append({"id": ex_id, "entity_type": "DIAGNOSIS", "payload": payload, "verification_status": "UNVERIFIED"})

    for d in entities["dates"]:
        ex_id = str(uuid.uuid4())
        payload = {"date": d}
        db.add(DocumentExtraction(
            id=ex_id, document_id=document.id, entity_type="DATE", payload_json=json.dumps(payload),
        ))

    # Timeline event
    db.add(TimelineEvent(
        patient_id=user.id,
        event_type="DOCUMENT",
        event_date=document.document_date,
        title=f"Document added: {document.filename}",
        detail=document.document_type or "Other",
        ref_id=document.id,
        source="OCR_EXTRACTED",
    ))

    # If session attached, recompute summary lazily (next time clinician opens it)
    if session_id:
        s = db.get(IntakeSession, session_id)
        if s and s.patient_id == user.id:
            # mark status so a clinician can re-review
            s.status = "REVIEW_REQUIRED"

    db.commit()
    log_audit(db, actor=user, action="DOCUMENT_UPLOADED", resource_type="document", resource_id=document.id, request=request,
              detail=json.dumps({"extractions": len(extraction_summary)}))

    return DocumentOut(
        id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        document_type=document.document_type,
        ocr_text=document.ocr_text,
        ocr_confidence=document.ocr_confidence,
        document_date=document.document_date,
        extractions=[ExtractionOut(**e) for e in extraction_summary],
        created_at=document.created_at,
    )


@router.get("/mine")
def list_my_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(MedicalDocument)
        .filter(MedicalDocument.patient_id == user.id)
        .order_by(MedicalDocument.created_at.desc())
        .all()
    )
    out = []
    for d in rows:
        out.append({
            "id": d.id,
            "filename": d.filename,
            "mime_type": d.mime_type,
            "document_type": d.document_type,
            "document_date": d.document_date,
            "ocr_provider": d.ocr_provider,
            "ocr_confidence": d.ocr_confidence,
            "extractions": [
                {"id": e.id, "entity_type": e.entity_type, "payload": json.loads(e.payload_json), "verification_status": e.verification_status}
                for e in d.extractions
            ],
            "created_at": d.created_at.isoformat(),
        })
    return ok(out)
