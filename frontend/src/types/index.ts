export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'PATIENT' | 'CLINICIAN' | 'ADMIN';
  phone?: string;
  preferred_language: string;
  abha_id?: string;
  date_of_birth?: string;
  gender?: string;
  blood_group?: string;
  specialty?: string;
  department?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Consent {
  id: string;
  consent_version: string;
  scope: string[];
  status: string;
  purpose: string;
  granted_at: string;
}

export interface IntakeSession {
  id: string;
  patient_id: string;
  language: string;
  mode: string;
  status: string;
  chief_complaint?: string;
  priority: string;
  started_at: string;
  submitted_at?: string;
  progress: number;
  total_questions: number;
}

export interface IntakeQuestion {
  code: string;
  domain: string;
  prompt: string;
  answer_type: string;
  options?: { value: string; label: string }[];
  required: boolean;
  progress: number;
  total: number;
}

export interface IntakeAnswer {
  id: string;
  question_code: string;
  answer_text?: string;
  answer_value?: any;
  source: string;
  created_at: string;
}

export interface DocumentExtraction {
  id: string;
  entity_type: string;
  payload: Record<string, any>;
  verification_status: string;
}

export interface MedicalDocument {
  id: string;
  filename: string;
  mime_type: string;
  document_type?: string;
  document_date?: string;
  ocr_text?: string;
  ocr_confidence?: number;
  ocr_provider?: string;
  extractions: DocumentExtraction[];
  created_at: string;
}

export interface RedFlag {
  id?: string;
  code: string;
  message: string;
  severity: string;
  triggered_by?: string[];
}

export interface ClinicalSummary {
  prose: string;
  structured: Record<string, any>;
  is_ai_generated: boolean;
  ai_provider: string;
  verification_status: string;
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  event_date?: string;
  title: string;
  detail?: string;
  source: string;
  ref_id?: string;
  created_at: string;
}

export interface DoctorNote {
  id: string;
  author_id: string;
  note_type: string;
  content: string;
  is_private: boolean;
  created_at: string;
}

export interface CaseDetail {
  session: {
    id: string;
    patient_id: string;
    language: string;
    mode: string;
    status: string;
    chief_complaint?: string;
    priority: string;
    started_at?: string;
    submitted_at?: string;
  };
  patient: {
    id: string;
    full_name: string;
    email: string;
    phone?: string;
    abha_id?: string;
    preferred_language: string;
    date_of_birth?: string;
    gender?: string;
    blood_group?: string;
  };
  abdm?: { abha_id: string; status: string };
  answers: IntakeAnswer[];
  summary?: ClinicalSummary;
  red_flags: RedFlag[];
  documents: MedicalDocument[];
  notes: DoctorNote[];
}

export interface QueueItem {
  session_id: string;
  patient_id: string;
  patient_name: string;
  patient_age?: number;
  patient_gender?: string;
  chief_complaint?: string;
  priority: string;
  status: string;
  submitted_at?: string;
  red_flag_count: number;
}

export interface DashboardCounts {
  new_cases: number;
  pending_review: number;
  priority_cases: number;
  completed_cases: number;
  today_queue: number;
}

export interface TimelineEventOut {
  id: string;
  event_type: string;
  event_date?: string;
  title: string;
  detail?: string;
  source: string;
  created_at: string;
}

export interface IntegrationStatus {
  abdm: { status: string; message: string };
  fhir: { status: string; message: string };
  his: { status: string; message: string };
  consent: { status: string; message: string };
}
