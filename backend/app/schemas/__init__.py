"""Pydantic v2 schemas (request/response models)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = None
    role: str = Field(default="PATIENT", pattern="^(PATIENT|CLINICIAN|ADMIN)$")
    preferred_language: str = Field(default="en", pattern="^(en|hi)$")
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    abha_id: Optional[str] = None
    specialty: Optional[str] = None
    registration_number: Optional[str] = None
    department: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    phone: Optional[str] = None
    preferred_language: str = "en"
    abha_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    specialty: Optional[str] = None
    department: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Consent ----------

class ConsentRequest(BaseModel):
    scope: List[str] = Field(default_factory=lambda: [
        "history", "documents", "ai_processing", "summary", "his_share", "abdm_share"
    ])
    purpose: Optional[str] = "Clinical intake and sharing with treating doctor"
    language: str = "en"


class ConsentOut(BaseModel):
    id: str
    consent_version: str
    scope: List[str]
    status: str
    purpose: str
    granted_at: datetime

    class Config:
        from_attributes = True


# ---------- Intake ----------

class IntakeStartRequest(BaseModel):
    language: str = Field(default="en", pattern="^(en|hi)$")
    mode: str = Field(default="STANDARD", pattern="^(STANDARD|AYUSH)$")
    consent_id: Optional[str] = None


class AnswerRequest(BaseModel):
    question_code: str
    answer_text: Optional[str] = None
    answer_value: Optional[Any] = None
    source: str = Field(default="PATIENT_TOUCH")
    question_category: Optional[str] = None
    clinical_data_extracted: Optional[dict] = None


class QuestionOut(BaseModel):
    code: str
    domain: str
    prompt: str
    answer_type: str
    options: Optional[List[Any]] = None
    required: bool = False
    progress: int = 0
    total: int = 0


class AnswerOut(BaseModel):
    id: str
    question_code: str
    answer_text: Optional[str]
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class IntakeSessionOut(BaseModel):
    id: str
    patient_id: str
    language: str
    mode: str
    status: str
    chief_complaint: Optional[str]
    priority: str
    started_at: datetime
    submitted_at: Optional[datetime]
    progress: int = 0
    total_questions: int = 0

    class Config:
        from_attributes = True


class IntakeSubmitRequest(BaseModel):
    final_chief_complaint: Optional[str] = None
    ayush: Optional[dict] = None  # for AYUSH mode submissions


# ---------- Documents ----------

class DocumentOut(BaseModel):
    id: str
    filename: str
    mime_type: str
    document_type: Optional[str]
    ocr_text: Optional[str]
    ocr_confidence: Optional[float]
    document_date: Optional[str]
    extractions: List["ExtractionOut"] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ExtractionOut(BaseModel):
    id: str
    entity_type: str
    payload: dict
    verification_status: str

    class Config:
        from_attributes = True


# ---------- Summary & timeline ----------

class RedFlagOut(BaseModel):
    code: str
    message: str
    severity: str


class SummaryOut(BaseModel):
    session_id: str
    prose: str
    structured: dict
    red_flags: List[RedFlagOut]
    is_ai_generated: bool
    ai_provider: str
    verification_status: str
    source_links: List[dict] = []


class TimelineEventOut(BaseModel):
    id: str
    event_type: str
    event_date: Optional[str]
    title: str
    detail: Optional[str]
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Clinician ----------

class CaseListItem(BaseModel):
    session_id: str
    patient_id: str
    patient_name: str
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    chief_complaint: Optional[str]
    priority: str
    status: str
    submitted_at: Optional[datetime]
    red_flag_count: int = 0


class DashboardCounts(BaseModel):
    new_cases: int
    pending_review: int
    priority_cases: int
    completed_cases: int
    today_queue: int


class NoteRequest(BaseModel):
    note_type: str = "CONSULTATION"
    content: str
    is_private: bool = False


class VerifyRequest(BaseModel):
    target_type: str
    target_id: str
    status: str  # VERIFIED, EDITED, REJECTED
    modified_value: Optional[str] = None


# ---------- FHIR / ABDM / HIS ----------

class FhirExportRequest(BaseModel):
    resource_types: Optional[List[str]] = None


class FhirExportResponse(BaseModel):
    exported: int
    resources: List[dict]


class IntegrationStatus(BaseModel):
    abdm: dict
    fhir: dict
    his: dict
    consent: dict


# Resolve forward refs
TokenResponse.model_rebuild()
DocumentOut.model_rebuild()
