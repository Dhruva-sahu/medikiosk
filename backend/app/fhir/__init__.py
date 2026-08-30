"""FHIR R4 mapping and export (with deterministic mock implementation)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    AbdmLink,
    AllergyRecord,
    FhirResource,
    IntakeSession,
    LabResult,
    MedicalDocument,
    MedicationRecord,
    PatientProfile,
    User,
)


# ---- FHIR R4 builders --------------------------------------------------

def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def build_patient_resource(patient: User) -> Dict[str, Any]:
    profile: Optional[PatientProfile] = patient.patient_profile
    name = (patient.full_name or "Unknown").split(" ", 1)
    given = [name[0]] if name else []
    family = name[1] if len(name) > 1 else ""
    resource = {
        "resourceType": "Patient",
        "id": patient.id,
        "identifier": [],
        "active": patient.is_active,
        "name": [{"use": "official", "family": family, "given": given}],
        "telecom": [{"system": "email", "value": patient.email}],
    }
    if patient.abha_id:
        resource["identifier"].append({
            "system": "https://healthid.ndhm.gov.in",
            "value": patient.abha_id,
        })
    if patient.phone:
        resource["telecom"].append({"system": "phone", "value": patient.phone})
    if profile:
        if profile.gender:
            resource["gender"] = profile.gender.lower()
        if profile.date_of_birth:
            resource["birthDate"] = profile.date_of_birth
    return resource


def build_observation_resource(lab: LabResult) -> Dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": lab.id,
        "status": "preliminary",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}],
        "code": {"text": lab.test_name},
        "subject": {"reference": f"Patient/{lab.patient_id}"},
        "effectiveDateTime": lab.test_date or _now_iso(),
        "valueQuantity": {"value": float(lab.value) if lab.value and lab.value.replace('.', '', 1).isdigit() else 0,
                          "unit": lab.unit or ""},
        "referenceRange": [{"text": lab.reference_range}] if lab.reference_range else [],
        "interpretation": [{"coding": [{"code": "H" if (lab.abnormal_flag or "").upper().startswith("H") else "L"}]}] if lab.abnormal_flag else [],
        "meta": {"source": "medikiosk", "verificationStatus": lab.verification_status},
    }


def build_medication_statement(med: MedicationRecord) -> Dict[str, Any]:
    return {
        "resourceType": "MedicationStatement",
        "id": med.id,
        "status": "active",
        "medicationCodeableConcept": {"text": med.name},
        "subject": {"reference": f"Patient/{med.patient_id}"},
        "dosage": [{"text": f"{med.dose or ''} {med.frequency or ''}".strip()}],
        "meta": {"source": "medikiosk", "verificationStatus": med.verification_status},
    }


def build_allergy_resource(allergy: AllergyRecord) -> Dict[str, Any]:
    return {
        "resourceType": "AllergyIntolerance",
        "id": allergy.id,
        "clinicalStatus": {"coding": [{"code": "active"}]},
        "code": {"text": allergy.substance},
        "patient": {"reference": f"Patient/{allergy.patient_id}"},
        "reaction": [{"manifestation": [{"text": allergy.reaction}]}] if allergy.reaction else [],
        "meta": {"source": "medikiosk", "verificationStatus": allergy.verification_status},
    }


def build_document_reference(doc: MedicalDocument) -> Dict[str, Any]:
    return {
        "resourceType": "DocumentReference",
        "id": doc.id,
        "status": "current",
        "subject": {"reference": f"Patient/{doc.patient_id}"},
        "date": doc.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if doc.created_at else _now_iso(),
        "type": {"text": doc.document_type or "OTHER"},
        "description": doc.filename,
        "content": [{"attachment": {"contentType": doc.mime_type, "title": doc.filename}}],
        "meta": {"source": "medikiosk"},
    }


# ---- Public service ----------------------------------------------------

class FhirService:
    def __init__(self, mode: str = "mock") -> None:
        self.mode = mode

    def export_for_patient(self, db: Session, patient_id: str) -> List[Dict[str, Any]]:
        """Build a complete FHIR bundle for a patient and persist FhirResource rows."""
        patient = db.get(User, patient_id)
        if not patient:
            return []
        bundle_resources: List[Dict[str, Any]] = []
        bundle_resources.append(build_patient_resource(patient))

        for med in db.query(MedicationRecord).filter_by(patient_id=patient_id).all():
            bundle_resources.append(build_medication_statement(med))
        for lab in db.query(LabResult).filter_by(patient_id=patient_id).all():
            bundle_resources.append(build_observation_resource(lab))
        for allergy in db.query(AllergyRecord).filter_by(patient_id=patient_id).all():
            bundle_resources.append(build_allergy_resource(allergy))
        for doc in db.query(MedicalDocument).filter_by(patient_id=patient_id).all():
            bundle_resources.append(build_document_reference(doc))

        # Persist (or update) each resource so they can be queried later.
        for r in bundle_resources:
            resource_id = r.get("id") or str(uuid.uuid4())
            r["id"] = resource_id
            existing = db.query(FhirResource).filter_by(resource_type=r["resourceType"], resource_id=resource_id).one_or_none()
            if existing:
                existing.payload_json = json.dumps(r)
                existing.created_at = datetime.utcnow()
            else:
                db.add(FhirResource(
                    patient_id=patient_id,
                    resource_type=r["resourceType"],
                    resource_id=resource_id,
                    payload_json=json.dumps(r),
                ))
        db.commit()
        return bundle_resources

    def get_patient_bundle(self, patient_id: str) -> Dict[str, Any]:
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": _now_iso(),
            "entry": [],  # populated by caller via export_for_patient
        }

    def status(self) -> Dict[str, Any]:
        if self.mode == "live":
            return {"status": "live", "base_url": "", "message": "Live FHIR server configured."}
        return {
            "status": "mock",
            "base_url": "mock://fhir",
            "message": "Deterministic mock FHIR service. No external data transmitted.",
        }


# Mock ABDM service - emits realistic ABHA/ABDM-style response
class AbdmService:
    def __init__(self, mode: str = "mock") -> None:
        self.mode = mode

    def link_abha(self, db: Session, patient: User, abha_id: str) -> AbdmLink:
        link = db.query(AbdmLink).filter_by(patient_id=patient.id).one_or_none()
        if not link:
            link = AbdmLink(patient_id=patient.id, abha_id=abha_id, status="MOCK_LINKED")
            db.add(link)
        else:
            link.abha_id = abha_id
            link.status = "MOCK_LINKED"
            link.last_synced_at = datetime.utcnow()
        db.commit()
        db.refresh(link)
        return link

    def status(self) -> Dict[str, Any]:
        if self.mode == "live":
            return {"status": "live", "message": "ABDM client configured."}
        return {
            "status": "mock",
            "abha_format": "XX-XXXX-XXXX-XXXX",
            "message": "Demo integration - no real patient data transmitted.",
        }


# Mock HIS push service
class HisService:
    def __init__(self, mode: str = "mock") -> None:
        self.mode = mode

    def push_encounter(self, db: Session, session: IntakeSession) -> Dict[str, Any]:
        return {
            "his_ack_id": str(uuid.uuid4()),
            "encounter_ref": session.id,
            "status": "queued",
            "message": "Mock HIS: encounter accepted into OPD queue.",
            "pushed_at": _now_iso(),
        }

    def status(self) -> Dict[str, Any]:
        if self.mode == "live":
            return {"status": "live", "message": "HIS endpoint configured."}
        return {"status": "mock", "message": "Demo HIS - encounters are queued locally only."}
