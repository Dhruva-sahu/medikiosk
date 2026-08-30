"""SQLAlchemy ORM models for Swasthya Setu.

All tables are designed against PostgreSQL semantics but work on SQLite
for development. UUIDs are used for primary keys.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ---------- Users & RBAC ----------

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="PATIENT", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    abha_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    patient_profile: Mapped[Optional["PatientProfile"]] = relationship(
        "PatientProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    clinician_profile: Mapped[Optional["ClinicianProfile"]] = relationship(
        "ClinicianProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class PatientProfile(Base):
    __tablename__ = "patient_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, index=True)
    date_of_birth: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    blood_group: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    emergency_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship("User", back_populates="patient_profile")


class ClinicianProfile(Base):
    __tablename__ = "clinician_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, index=True)
    specialty: Mapped[str] = mapped_column(String(128), default="General Medicine")
    registration_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship("User", back_populates="clinician_profile")


# ---------- Consent ----------

class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    consent_version: Mapped[str] = mapped_column(String(16), default="v1.0")
    scope: Mapped[str] = mapped_column(Text)  # JSON list of granted scopes
    status: Mapped[str] = mapped_column(String(16), default="GRANTED")
    purpose: Mapped[str] = mapped_column(Text, default="")
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# ---------- Intake & Clinical History ----------

class IntakeSession(Base):
    """A single kiosk intake session for a patient encounter."""
    __tablename__ = "intake_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    mode: Mapped[str] = mapped_column(String(16), default="STANDARD")
    consent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("consents.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="IN_PROGRESS")
    chief_complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conversation_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: [{role, content}]
    collected_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: structured clinical data
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[str] = mapped_column(String(16), default="NORMAL")
    assigned_clinician_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    answers: Mapped[List["IntakeAnswer"]] = relationship(
        "IntakeAnswer", back_populates="session", cascade="all, delete-orphan"
    )
    documents: Mapped[List["MedicalDocument"]] = relationship(
        "MedicalDocument", back_populates="session", cascade="all, delete-orphan"
    )
    summary: Mapped[Optional["ClinicalSummary"]] = relationship(
        "ClinicalSummary", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    red_flags: Mapped[List["RedFlag"]] = relationship(
        "RedFlag", back_populates="session", cascade="all, delete-orphan"
    )
    notes: Mapped[List["DoctorNote"]] = relationship(
        "DoctorNote", back_populates="session", cascade="all, delete-orphan"
    )


class IntakeQuestion(Base):
    """Question catalogue used by the adaptive engine."""
    __tablename__ = "intake_questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)
    prompt_en: Mapped[str] = mapped_column(Text)
    prompt_hi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer_type: Mapped[str] = mapped_column(String(16), default="text")
    options_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)


class IntakeAnswer(Base):
    __tablename__ = "intake_answers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("intake_sessions.id"), index=True)
    question_code: Mapped[str] = mapped_column(String(64))
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="PATIENT_TOUCH")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped[IntakeSession] = relationship("IntakeSession", back_populates="answers")


# ---------- Structured clinical data ----------

class MedicalHistoryItem(Base):
    __tablename__ = "medical_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(255))
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="PATIENT_PROVIDED")
    source_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MedicationRecord(Base):
    __tablename__ = "medications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    dose: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="PATIENT_PROVIDED")
    source_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AllergyRecord(Base):
    __tablename__ = "allergies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    substance: Mapped[str] = mapped_column(String(128))
    reaction: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="PATIENT_PROVIDED")
    verification_status: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class LabResult(Base):
    __tablename__ = "lab_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    test_name: Mapped[str] = mapped_column(String(128))
    value: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reference_range: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    abnormal_flag: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    test_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="OCR_EXTRACTED")
    source_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ---------- AYUSH ----------

class AyushAssessment(Base):
    __tablename__ = "ayush_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("intake_sessions.id"), nullable=True)
    prakriti: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    vikriti: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sara: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    samhanana: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pramana: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    satmya: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sattva: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ahara_shakti: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    vyayama_shakti: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    vaya: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ahara: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vihara: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nidana: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    samprapti: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ---------- Documents & OCR ----------

class MedicalDocument(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("intake_sessions.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(512))
    document_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ocr_provider: Mapped[str] = mapped_column(String(32), default="mock")
    document_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped[Optional[IntakeSession]] = relationship("IntakeSession", back_populates="documents")
    extractions: Mapped[List["DocumentExtraction"]] = relationship(
        "DocumentExtraction", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentExtraction(Base):
    """A single entity extracted from a document, with source traceability."""
    __tablename__ = "document_extractions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    document: Mapped[MedicalDocument] = relationship("MedicalDocument", back_populates="extractions")


# ---------- Clinical summary & red flags ----------

class ClinicalSummary(Base):
    __tablename__ = "clinical_summaries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("intake_sessions.id"), unique=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    structured_json: Mapped[str] = mapped_column(Text)
    prose: Mapped[str] = mapped_column(Text)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_provider: Mapped[str] = mapped_column(String(32), default="mock")
    verification_status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    edited_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    session: Mapped[IntakeSession] = relationship("IntakeSession", back_populates="summary")


class RedFlag(Base):
    __tablename__ = "red_flags"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("intake_sessions.id"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="HIGH")
    triggered_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped[IntakeSession] = relationship("IntakeSession", back_populates="red_flags")


# ---------- Clinician workflow ----------

class DoctorNote(Base):
    __tablename__ = "doctor_notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("intake_sessions.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    note_type: Mapped[str] = mapped_column(String(32), default="CONSULTATION")
    content: Mapped[str] = mapped_column(Text)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped[IntakeSession] = relationship("IntakeSession", back_populates="notes")


class VerificationRecord(Base):
    """Captures the human-in-the-loop verification of any AI/OCR field."""
    __tablename__ = "verification_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    original_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modified_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    event_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ref_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="PATIENT_PROVIDED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ---------- ABDM / FHIR ----------

class AbdmLink(Base):
    __tablename__ = "abdm_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    abha_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="MOCK_LINKED")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class FhirResource(Base):
    __tablename__ = "fhir_resources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="medikiosk")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (UniqueConstraint("resource_type", "resource_id", name="uq_fhir_resource"),)


# ---------- Notifications & audit ----------

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="INFO")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


__all__ = [
    "User",
    "PatientProfile",
    "ClinicianProfile",
    "Consent",
    "IntakeSession",
    "IntakeQuestion",
    "IntakeAnswer",
    "MedicalHistoryItem",
    "MedicationRecord",
    "AllergyRecord",
    "LabResult",
    "AyushAssessment",
    "MedicalDocument",
    "DocumentExtraction",
    "ClinicalSummary",
    "RedFlag",
    "DoctorNote",
    "VerificationRecord",
    "TimelineEvent",
    "AbdmLink",
    "FhirResource",
    "Notification",
    "AuditLog",
]
