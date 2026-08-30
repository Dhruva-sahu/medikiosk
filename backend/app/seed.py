"""Seed demo users, a fully populated Ananya case, and a priority case.

Run with:  python -m app.seed
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.ai import (
    detect_red_flags_from_conversation,
    structured_from_conversation,
)
from app.db import SessionLocal, init_db
from app.models import (
    AbdmLink,
    AyushAssessment,
    ClinicalSummary,
    Consent,
    DoctorNote,
    DocumentExtraction,
    IntakeAnswer,
    IntakeSession,
    LabResult,
    MedicalDocument,
    MedicalHistoryItem,
    MedicationRecord,
    PatientProfile,
    RedFlag,
    TimelineEvent,
    User,
)
from app.ocr import extract_medical_entities
from app.security import hash_password
from app.ai.provider import get_ai_provider
from sqlalchemy import inspect

logger = logging.getLogger(__name__)


DEMO_PASSWORD = "demo1234"


# -------------------------- Demo data ---------------------------------

PATIENTS = [
    {
        "email": "ananya@demo.medikiosk",
        "full_name": "Ananya Sharma",
        "phone": "+91 98765 43210",
        "date_of_birth": "1991-04-12",
        "gender": "female",
        "blood_group": "B+",
        "abha_id": "12-3456-7890-1234",
        "address": "Flat 12B, Sea Breeze Apartments, Mumbai",
        "chief_complaint": "I have been having recurring headaches for the last two weeks.",
    },
    {
        "email": "demo003@demo.medikiosk",
        "full_name": "Demo Patient 003",
        "phone": "+91 99887 76655",
        "date_of_birth": "1962-08-30",
        "gender": "male",
        "blood_group": "O+",
        "abha_id": "98-7654-3210-9876",
        "address": "Sector 9, NIT Campus",
        "chief_complaint": "Severe chest discomfort and difficulty breathing since this morning.",
        "priority": True,
    },
    {
        "email": "demo002@demo.medikiosk",
        "full_name": "Demo Patient 002",
        "phone": "+91 90123 45678",
        "date_of_birth": "1995-02-14",
        "gender": "female",
        "blood_group": "A+",
        "address": "Greenfield Colony",
        "chief_complaint": "Routine follow-up for seasonal allergies.",
    },
]

CLINICIANS = [
    {
        "email": "doctor@demo.medikiosk",
        "full_name": "Dr. R. Mehta",
        "specialty": "Internal Medicine",
        "registration_number": "MH/2014/1234",
        "department": "OPD - General Medicine",
    },
    {
        "email": "ayush@demo.medikiosk",
        "full_name": "Dr. Kavita Iyer",
        "specialty": "Ayurveda (BAMS)",
        "registration_number": "KA/2018/5678",
        "department": "AYUSH OPD",
    },
]


# -------------------------- Seeders -----------------------------------

def _ensure_user(db: Session, *, email: str, full_name: str, role: str, **extra) -> User:
    u = db.query(User).filter(User.email == email).one_or_none()
    if u:
        return u
    u = User(
        email=email,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name=full_name,
        role=role,
        phone=extra.get("phone"),
        abha_id=extra.get("abha_id"),
    )
    db.add(u)
    db.flush()
    return u


def _ensure_patient_profile(db: Session, user: User, **kwargs) -> PatientProfile:
    p = db.query(PatientProfile).filter_by(user_id=user.id).one_or_none()
    if not p:
        p = PatientProfile(user_id=user.id, **kwargs)
        db.add(p)
        db.flush()
    else:
        for k, v in kwargs.items():
            setattr(p, k, v)
    return p


def _ensure_consent(db: Session, user: User) -> Consent:
    c = db.query(Consent).filter_by(patient_id=user.id, status="GRANTED").order_by(Consent.granted_at.desc()).first()
    if not c:
        c = Consent(
            patient_id=user.id,
            scope='["history","documents","ai_processing","summary","his_share","abdm_share"]',
            purpose="Seed demo consent",
        )
        db.add(c)
        db.flush()
    return c


def _add_answer(db: Session, session: IntakeSession, code: str, text: str, source: str = "PATIENT_TOUCH") -> IntakeAnswer:
    a = IntakeAnswer(session_id=session.id, question_code=code, answer_text=text, source=source)
    db.add(a)
    return a


def _seed_documents_for_session(db: Session, session: IntakeSession, *, patient: User, docs: List[dict]) -> None:
    for d in docs:
        existing = db.query(MedicalDocument).filter_by(patient_id=patient.id, filename=d["filename"]).first()
        if existing:
            existing.session_id = session.id
            continue
        entities = extract_medical_entities(d["text"])
        doc = MedicalDocument(
            patient_id=patient.id,
            session_id=session.id,
            filename=d["filename"],
            mime_type=d["mime_type"],
            storage_path=str(Path("./uploads/documents") / d["filename"]),
            document_type=d["document_type"],
            ocr_text=d["text"],
            ocr_confidence=d["confidence"],
            ocr_provider="mock",
            document_date=entities.get("document_date") or d.get("document_date"),
        )
        db.add(doc)
        db.flush()

        for med in entities["medications"]:
            db.add(MedicationRecord(
                patient_id=patient.id,
                name=med["name"],
                dose=f"{med['dose']} {med['unit']}".strip(),
                source="OCR_EXTRACTED", source_ref=doc.id,
            ))
            db.add(DocumentExtraction(
                document_id=doc.id, entity_type="MEDICATION",
                payload_json=json.dumps({"name": med["name"], "dose": med["dose"], "unit": med["unit"]}),
            ))
        for lab in entities["lab_values"]:
            db.add(LabResult(
                patient_id=patient.id,
                test_name=lab["test_name"],
                value=lab["value"], unit=lab["unit"],
                reference_range=lab["reference_range"],
                abnormal_flag=lab["abnormal_flag"],
                test_date=doc.document_date,
                source="OCR_EXTRACTED", source_ref=doc.id,
            ))
            db.add(DocumentExtraction(
                document_id=doc.id, entity_type="LAB",
                payload_json=json.dumps(lab),
            ))
        for diag in entities["diagnoses"]:
            db.add(MedicalHistoryItem(
                patient_id=patient.id, category="PAST_MEDICAL",
                label=diag["label"], detail=diag["evidence"],
                source="OCR_EXTRACTED", source_ref=doc.id,
            ))
            db.add(DocumentExtraction(
                document_id=doc.id, entity_type="DIAGNOSIS",
                payload_json=json.dumps(diag),
            ))
        for x in entities["dates"]:
            db.add(DocumentExtraction(
                document_id=doc.id, entity_type="DATE",
                payload_json=json.dumps({"date": x}),
            ))
        db.add(TimelineEvent(
            patient_id=patient.id, event_type="DOCUMENT", event_date=doc.document_date,
            title=f"Document: {doc.filename}", detail=doc.document_type or "Other",
            ref_id=doc.id, source="OCR_EXTRACTED",
        ))


# ------------------ Specific demo case builders ------------------------

def _build_ananya_case(db: Session, patient: User) -> None:
    existing = db.query(IntakeSession).filter_by(patient_id=patient.id).first()
    if existing:
        return
    consent = _ensure_consent(db, patient)
    s = IntakeSession(
        patient_id=patient.id, language="en", mode="STANDARD",
        consent_id=consent.id, status="REVIEW_REQUIRED", priority="NORMAL",
        submitted_at=datetime.utcnow() - timedelta(hours=2),
    )
    s.chief_complaint = "Recurring headaches for the last two weeks"
    db.add(s)
    db.flush()

    # Answers covering SOCRATES + standard history
    answers = {
        "CHIEF_COMPLAINT": "I have been having recurring headaches for the last two weeks.",
        "HPI_ONSET": "Started about 14 days ago",
        "HPI_DURATION": "Each episode lasts 2-4 hours",
        "HPI_LOCATION": "Mostly on the right side, around the temple",
        "HPI_CHARACTER": "Throbbing",
        "HPI_SEVERITY": "6",
        "HPI_RADIATION": "Sometimes radiates to the back of the neck",
        "HPI_ASSOCIATED": "Mild nausea, sensitivity to bright light",
        "HPI_AGGRAVATING": "Stress, lack of sleep, bright screens",
        "HPI_RELIEVING": "Resting in a dark room, paracetamol helps partially",
        "HPI_TIMING": "Comes and goes - about 4-5 episodes a week",
        "PMH": "Mild iron-deficiency anaemia diagnosed last year",
        "PSH": "Appendicectomy in 2015",
        "DRUG_HISTORY": "Iron + Folic acid tablet, Vitamin D3 sachet weekly",
        "ALLERGY": "Mild seasonal allergic rhinitis (dust mites)",
        "FAMILY_HISTORY": "Father has hypertension, mother has type 2 diabetes",
        "PERSONAL_SMOKING": "no",
        "PERSONAL_ALCOHOL": "occasional",
        "ROS_GENERAL": "fatigue",
    }
    for code, txt in answers.items():
        _add_answer(db, s, code, txt, source="VOICE_TRANSCRIBED" if code != "CHIEF_COMPLAINT" else "PATIENT_TOUCH")

    # Documents for Ananya
    _seed_documents_for_session(db, s, patient=patient, docs=[
        {
            "filename": "prescription-2026-08-10.png",
            "mime_type": "image/png",
            "document_type": "PRESCRIPTION",
            "confidence": 0.94,
            "text": (
                "PRESCRIPTION\n"
                "Dr. R. Mehta, MBBS MD (Internal Medicine)\n"
                "Reg. No: MH/2014/1234   Date: 2026-08-10\n"
                "Patient: Ananya Sharma   Age: 34   Sex: F\n\n"
                "Rx\n"
                "1. Tab. Metformin 500 mg - 1-0-1 (after meals) x 30 days\n"
                "2. Tab. Atorvastatin 10 mg - 0-0-1 (after dinner) x 30 days\n"
                "3. Tab. Vitamin D3 60K IU - 1 sachet weekly x 8 weeks\n"
                "4. Tab. Iron + Folic acid - 1-0-0 x 30 days\n"
                "Advice: Low fat diet, brisk walk 30 min/day, repeat HbA1c after 3 months.\n"
            ),
        },
        {
            "filename": "lab-report-2026-08-15.png",
            "mime_type": "image/png",
            "document_type": "LAB_REPORT",
            "confidence": 0.92,
            "text": (
                "City Pathology Laboratory\n"
                "Patient Name: Ananya Sharma   Age: 34   Sex: F\n"
                "Referred by: Dr. Verma\n"
                "Date of collection: 2026-08-15\n\n"
                "COMPLETE BLOOD COUNT\n"
                "Hemoglobin         11.2 g/dL     (12.0 - 15.5)   LOW\n"
                "WBC count          7800 /cumm    (4000 - 11000)\n"
                "Platelet count     2.1 lakh/cumm (1.5 - 4.0)\n"
                "RBC count          4.1 million/cumm (3.8 - 4.8)\n\n"
                "LIPID PROFILE\n"
                "Total Cholesterol  214 mg/dL     (< 200)         HIGH\n"
                "Triglycerides      168 mg/dL     (< 150)         HIGH\n"
                "HDL                38 mg/dL      (> 40)          LOW\n"
                "LDL                142 mg/dL     (< 100)         HIGH\n"
            ),
        },
        {
            "filename": "discharge-summary-2026-06-12.png",
            "mime_type": "image/png",
            "document_type": "DISCHARGE_SUMMARY",
            "confidence": 0.90,
            "text": (
                "DISCHARGE SUMMARY\n"
                "Apollo Hospital, Mumbai\n"
                "Patient: Ananya Sharma  Age: 34  Sex: F  UHID: 900123\n"
                "Date of admission: 2026-06-10\n"
                "Date of discharge: 2026-06-12\n"
                "Diagnosis: Acute viral fever with thrombocytopenia\n"
                "Procedure: Conservative management, IV fluids\n"
                "Advised: CBC repeat after 2 weeks, plenty of fluids, paracetamol SOS\n"
            ),
        },
    ])

    # AYUSH history on file (Ananya also consulted the AYUSH OPD earlier)
    db.add(AyushAssessment(
        patient_id=patient.id, session_id=s.id,
        prakriti="Pitta-Vata", vikriti="Vata aggravation",
        sara="Moderate", samhanana="Moderate", pramana="162 cm / 58 kg",
        satmya="Mixed", sattva="Moderate", ahara_shakti="Moderate",
        vyayama_shakti="Low", vaya="Young adult",
        ahara="Vegetarian, late dinners, frequent tea/coffee",
        vihara="Sedentary job, sleep 5-6 hours, irregular meals",
        nidana="Irregular sleep and high stress suspected",
        samprapti="Vata aggravating due to irregular routines, manifesting as recurrent headaches",
    ))

    # Build clinical summary using provider
    history = [{"role": "patient", "content": a.answer_text} for a in s.answers]
    collected = {}
    structured = structured_from_conversation(history, collected, s.chief_complaint)
    structured["ayush"] = {
        "prakriti": "Pitta-Vata", "vikriti": "Vata aggravation",
        "ahara": "Vegetarian, late dinners, frequent tea/coffee",
        "vihara": "Sedentary job, sleep 5-6 hours, irregular meals",
    }
    docs_summary = []
    for d in db.query(MedicalDocument).filter_by(patient_id=patient.id).all():
        docs_summary.append({
            "id": d.id, "filename": d.filename, "type": d.document_type,
            "date": d.document_date,
            "extractions": [
                {"entity_type": e.entity_type, "payload": json.loads(e.payload_json)}
                for e in d.extractions
            ],
        })
    provider = get_ai_provider()
    result = provider.summarise(structured=structured, documents=docs_summary, red_flags=[])
    db.add(ClinicalSummary(
        session_id=s.id, patient_id=patient.id,
        structured_json=json.dumps(structured), prose=result["summary_text"],
        is_ai_generated=result.get("is_ai_generated", False),
        ai_provider=result.get("provider", "mock"), verification_status="DRAFT",
    ))

    # Timeline
    db.add(TimelineEvent(
        patient_id=patient.id, event_type="INTAKE",
        event_date=datetime.utcnow().strftime("%Y-%m-%d"),
        title="Clinical intake completed",
        detail=s.chief_complaint, ref_id=s.id, source="MEDIKIOSK",
    ))

    # ABDM mock link
    db.add(AbdmLink(patient_id=patient.id, abha_id=patient.abha_id, status="MOCK_LINKED",
                    last_synced_at=datetime.utcnow()))

    # A clinician note from a prior review
    clinician = db.query(User).filter_by(email="doctor@demo.medikiosk").first()
    if clinician:
        db.add(DoctorNote(
            session_id=s.id, author_id=clinician.id, note_type="ASSESSMENT",
            content="Patient appears stable. Review lipid panel trend and check BP today.",
        ))


def _build_priority_case(db: Session, patient: User) -> None:
    existing = db.query(IntakeSession).filter_by(patient_id=patient.id).first()
    if existing:
        return
    consent = _ensure_consent(db, patient)
    s = IntakeSession(
        patient_id=patient.id, language="en", mode="STANDARD",
        consent_id=consent.id, status="REVIEW_REQUIRED", priority="PRIORITY",
        submitted_at=datetime.utcnow() - timedelta(minutes=20),
    )
    s.chief_complaint = "Severe chest discomfort and difficulty breathing"
    db.add(s)
    db.flush()

    answers = {
        "CHIEF_COMPLAINT": "Severe chest discomfort and difficulty breathing since this morning.",
        "HPI_ONSET": "About 4 hours ago, while climbing stairs",
        "HPI_DURATION": "Constant since onset",
        "HPI_LOCATION": "Centre of the chest",
        "HPI_CHARACTER": "Heavy pressure-like",
        "HPI_SEVERITY": "9",
        "HPI_RADIATION": "Yes, radiates to the left arm",
        "HPI_ASSOCIATED": "Profuse sweating, breathlessness, mild nausea",
        "HPI_AGGRAVATING": "Any exertion",
        "HPI_RELIEVING": "Resting a little, but not fully",
        "HPI_TIMING": "Constant",
        "PMH": "Type 2 diabetes for 8 years, Hypertension for 5 years",
        "PSH": "CABG surgery 3 years ago",
        "DRUG_HISTORY": "Tab. Aspirin 75 mg, Tab. Atorvastatin 20 mg, Tab. Metformin 1000 mg BD",
        "ALLERGY": "No known drug allergies",
        "FAMILY_HISTORY": "Father had a heart attack at age 60",
        "PERSONAL_SMOKING": "former",
        "PERSONAL_ALCOHOL": "no",
        "ROS_GENERAL": "fever",
    }
    for code, txt in answers.items():
        _add_answer(db, s, code, txt, source="PATIENT_TOUCH")

    _seed_documents_for_session(db, s, patient=patient, docs=[
        {
            "filename": "discharge-cabg-2023.png",
            "mime_type": "image/png",
            "document_type": "DISCHARGE_SUMMARY",
            "confidence": 0.91,
            "text": (
                "DISCHARGE SUMMARY\n"
                "City Heart Institute\n"
                "Patient: Demo Patient 003   Age: 60   Sex: M\n"
                "Date of admission: 2023-04-18\n"
                "Date of discharge: 2023-04-25\n"
                "Diagnosis: Acute MI, post-CABG\n"
                "Procedure: Coronary Artery Bypass Graft x 3\n"
                "Discharge meds: Tab. Aspirin 75 mg OD, Tab. Atorvastatin 20 mg HS, Tab. Metoprolol 25 mg BD\n"
            ),
        },
    ])

    # Red flags (priority)
    history = [{"role": "patient", "content": a.answer_text} for a in s.answers]
    collected = {}
    flags = detect_red_flags_from_conversation(history, collected)
    for f in flags:
        db.add(RedFlag(
            session_id=s.id, code=f["code"], message=f["message"], severity=f.get("severity", "HIGH"),
            triggered_by=json.dumps(f.get("triggered_by", [])),
        ))

    history = [{"role": "patient", "content": a.answer_text} for a in s.answers]
    collected = {}
    structured = structured_from_conversation(history, collected, s.chief_complaint)
    docs_summary = []
    for d in db.query(MedicalDocument).filter_by(patient_id=patient.id).all():
        docs_summary.append({
            "id": d.id, "filename": d.filename, "type": d.document_type,
            "date": d.document_date,
            "extractions": [
                {"entity_type": e.entity_type, "payload": json.loads(e.payload_json)}
                for e in d.extractions
            ],
        })
    provider = get_ai_provider()
    result = provider.summarise(structured=structured, documents=docs_summary, red_flags=flags)
    db.add(ClinicalSummary(
        session_id=s.id, patient_id=patient.id,
        structured_json=json.dumps(structured), prose=result["summary_text"],
        is_ai_generated=False, ai_provider="mock", verification_status="DRAFT",
    ))
    db.add(TimelineEvent(
        patient_id=patient.id, event_type="INTAKE",
        event_date=datetime.utcnow().strftime("%Y-%m-%d"),
        title="PRIORITY intake", detail=s.chief_complaint, ref_id=s.id, source="MEDIKIOSK",
    ))
    db.add(AbdmLink(patient_id=patient.id, abha_id=patient.abha_id, status="MOCK_LINKED",
                    last_synced_at=datetime.utcnow()))


def _build_routine_case(db: Session, patient: User) -> None:
    existing = db.query(IntakeSession).filter_by(patient_id=patient.id).first()
    if existing:
        return
    consent = _ensure_consent(db, patient)
    s = IntakeSession(
        patient_id=patient.id, language="en", mode="STANDARD",
        consent_id=consent.id, status="COMPLETED", priority="NORMAL",
        submitted_at=datetime.utcnow() - timedelta(days=1),
    )
    s.chief_complaint = "Routine follow-up for seasonal allergies"
    db.add(s)
    db.flush()
    _add_answer(db, s, "CHIEF_COMPLAINT", "Routine follow-up for seasonal allergies.", source="PATIENT_TOUCH")
    _add_answer(db, s, "HPI_ONSET", "Symptoms have been stable since last visit.")
    _add_answer(db, s, "DRUG_HISTORY", "Tab. Cetirizine 10 mg SOS")
    history = [{"role": "patient", "content": a.answer_text} for a in s.answers]
    collected = {}
    structured = structured_from_conversation(history, collected, s.chief_complaint)
    provider = get_ai_provider()
    result = provider.summarise(structured=structured, documents=[], red_flags=[])
    db.add(ClinicalSummary(
        session_id=s.id, patient_id=patient.id,
        structured_json=json.dumps(structured), prose=result["summary_text"],
        is_ai_generated=False, ai_provider="mock", verification_status="CLINICIAN_VERIFIED",
    ))
    db.add(TimelineEvent(
        patient_id=patient.id, event_type="INTAKE",
        event_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
        title="Routine follow-up", detail=s.chief_complaint, ref_id=s.id, source="MEDIKIOSK",
    ))


# ------------------------- Entry point --------------------------------

def run() -> None:
    init_db()

    with SessionLocal() as db:
        # Clinicians
        for c in CLINICIANS:
            u = _ensure_user(db, email=c["email"], full_name=c["full_name"], role="CLINICIAN")
            from app.models import ClinicianProfile
            cp = db.query(ClinicianProfile).filter_by(user_id=u.id).one_or_none()
            if not cp:
                db.add(ClinicianProfile(
                    user_id=u.id, specialty=c["specialty"],
                    registration_number=c["registration_number"], department=c["department"],
                ))

        # Admin
        admin = _ensure_user(db, email="admin@demo.medikiosk", full_name="Swasthya Setu Admin", role="ADMIN")

        # Patients
        ananya = _ensure_user(
            db, email=PATIENTS[0]["email"], full_name=PATIENTS[0]["full_name"], role="PATIENT",
            phone=PATIENTS[0]["phone"], abha_id=PATIENTS[0]["abha_id"],
        )
        _ensure_patient_profile(
            db, ananya,
            date_of_birth=PATIENTS[0]["date_of_birth"], gender=PATIENTS[0]["gender"],
            blood_group=PATIENTS[0]["blood_group"], address=PATIENTS[0]["address"],
        )
        priority = _ensure_user(
            db, email=PATIENTS[1]["email"], full_name=PATIENTS[1]["full_name"], role="PATIENT",
            phone=PATIENTS[1]["phone"], abha_id=PATIENTS[1]["abha_id"],
        )
        _ensure_patient_profile(
            db, priority,
            date_of_birth=PATIENTS[1]["date_of_birth"], gender=PATIENTS[1]["gender"],
            blood_group=PATIENTS[1]["blood_group"], address=PATIENTS[1]["address"],
        )
        routine = _ensure_user(
            db, email=PATIENTS[2]["email"], full_name=PATIENTS[2]["full_name"], role="PATIENT",
            phone=PATIENTS[2]["phone"],
        )
        _ensure_patient_profile(
            db, routine,
            date_of_birth=PATIENTS[2]["date_of_birth"], gender=PATIENTS[2]["gender"],
            blood_group=PATIENTS[2]["blood_group"], address=PATIENTS[2]["address"],
        )

        _build_ananya_case(db, ananya)
        _build_priority_case(db, priority)
        _build_routine_case(db, routine)

        db.commit()
        logger.info("Seed complete. Demo users (password: %s):", DEMO_PASSWORD)
        for c in CLINICIANS:
            logger.info("  Clinician -> %s", c["email"])
        logger.info("  Admin     -> admin@demo.medikiosk")
        for p in PATIENTS:
            logger.info("  Patient   -> %s", p["email"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    run()
