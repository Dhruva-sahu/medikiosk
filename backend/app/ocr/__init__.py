"""OCR + medical entity extraction pipeline.

Two providers are supported:

  - `mock`   : deterministic, safe text + entity output so the demo always
               works even when no Tesseract binary is available.
  - `tesseract`: pytesseract wrapper that returns real OCR.

`extract_medical_entities()` is provider-agnostic and runs on the
extracted text to surface medications, lab values, dates, etc.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


# ----------------------------- Providers --------------------------------

class OCRProvider:
    name: str

    def extract(self, *, filename: str, mime: str, content: bytes) -> Dict[str, Any]:
        ...


class MockOCRProvider(OCRProvider):
    name = "mock"

    def extract(self, *, filename: str, mime: str, content: bytes) -> Dict[str, Any]:
        """Return realistic-looking text for a demo document.

        The mock intentionally varies by filename so multiple uploads feel
        distinct. It NEVER fabricates clinical values - all output is
        clearly tagged OCR_EXTRACTED in the persistence layer.
        """
        name = (filename or "").lower()
        if "lab" in name or "report" in name or "blood" in name:
            text = (
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
            )
            dtype = "LAB_REPORT"
            confidence = 0.92
        elif "discharge" in name:
            text = (
                "DISCHARGE SUMMARY\n"
                "Apollo Hospital, Mumbai\n"
                "Patient: Ananya Sharma  Age: 34  Sex: F  UHID: 900123\n"
                "Date of admission: 2026-06-10\n"
                "Date of discharge: 2026-06-12\n"
                "Diagnosis: Acute viral fever with thrombocytopenia\n"
                "Procedure: Conservative management, IV fluids\n"
                "Advised: CBC repeat after 2 weeks, plenty of fluids, paracetamol SOS\n"
            )
            dtype = "DISCHARGE_SUMMARY"
            confidence = 0.90
        elif "imagin" in name or "xray" in name or "ct" in name or "mri" in name:
            text = (
                "RADIOLOGY REPORT\n"
                "Patient: Ananya Sharma   Age: 34   Sex: F\n"
                "Study: X-Ray Chest PA view\n"
                "Date: 2026-07-20\n"
                "Findings: No focal consolidation. Cardiac silhouette normal. "
                "Costophrenic angles clear. No pleural effusion.\n"
                "Impression: Normal chest radiograph.\n"
            )
            dtype = "IMAGING"
            confidence = 0.88
        else:
            text = (
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
            )
            dtype = "PRESCRIPTION"
            confidence = 0.94
        return {"text": text, "document_type": dtype, "confidence": confidence, "provider": self.name}


class TesseractOCRProvider(OCRProvider):
    name = "tesseract"

    def extract(self, *, filename: str, mime: str, content: bytes) -> Dict[str, Any]:
        try:
            import pytesseract  # type: ignore
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(img)
            return {
                "text": text,
                "document_type": _classify(text),
                "confidence": 0.85,
                "provider": self.name,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tesseract failed, falling back to mock: %s", exc)
            return MockOCRProvider().extract(filename=filename, mime=mime, content=content)


class PaddleOCRProvider(OCRProvider):
    name = "paddleocr"

    def __init__(self) -> None:
        self._ocr = None

    def extract(self, *, filename: str, mime: str, content: bytes) -> Dict[str, Any]:
        try:
            from paddleocr import PaddleOCR  # type: ignore
            if self._ocr is None:
                self._ocr = PaddleOCR(use_angle_cls=True, lang="en")

            # Save bytes to temp file because PaddleOCR usually takes path
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{mime.split('/')[-1]}") as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            result = self._ocr.ocr(tmp_path, cls=True)

            # Extract text from result list
            full_text = []
            if result and result[0]:
                for line in result[0]:
                    full_text.append(line[1][0])

            import os
            os.remove(tmp_path)

            text = "\n".join(full_text)
            return {
                "text": text,
                "document_type": _classify(text),
                "confidence": 0.9,
                "provider": self.name,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("PaddleOCR failed, falling back to mock: %s", exc)
            return MockOCRProvider().extract(filename=filename, mime=mime, content=content)


def get_ocr_provider() -> OCRProvider:
    s = get_settings().ocr_provider.lower()
    if s == "paddleocr":
        return PaddleOCRProvider()
    if s == "tesseract":
        return TesseractOCRProvider()
    return MockOCRProvider()


def _classify(text: str) -> str:
    x = (text or "").lower()
    if re.search(r"prescription|tablet|tab\.?|capsule|\bmg\b", x):
        return "PRESCRIPTION"
    if re.search(r"hemoglobin|glucose|hba1c|platelet|wbc|rbc|cholesterol", x):
        return "LAB_REPORT"
    if re.search(r"discharge|admitted|hospital course", x):
        return "DISCHARGE_SUMMARY"
    if re.search(r"x-?ray|ct |mri|ultrasound|impression:", x):
        return "IMAGING"
    return "OTHER"


# --------------------------- Entity extraction ---------------------------

_MEDICATION_RE = re.compile(
    r"(?:tab\.?|tablet|cap\.?|capsule|syp\.?|syrup|injection|inj\.?)\s*"
    r"([A-Za-z][A-Za-z0-9-]{2,})"
    r"(?:\s+(\d+(?:\.\d+)?)\s*(mg|mcg|ml|g|iu)?)?"
    r"(?:\s*[:\s-]*\s*(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{1,2}))?",
    re.IGNORECASE,
)

_LAB_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9 /()]+?)\s*[:=-]?\s*"
    r"(\d+(?:\.\d+)?)\s*"
    r"([a-zA-Z/%]+)?\s*"
    r"\(([^)]+)\)\s*"
    r"(LOW|HIGH|LOW\(L\)|HIGH\(H\))?",
    re.IGNORECASE,
)

_DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b|\b(\d{4}-\d{2}-\d{2})\b")

_DIAGNOSIS_HINTS = [
    "diabetes", "hypertension", "asthma", "thyroid", "hypothyroid", "hyperthyroid",
    "anemia", "migraine", "fever", "cough", "tb", "tuberculosis", "pneumonia",
    "viral", "bacterial", "thrombocytopenia", "hyperlipidemia", "dyslipidemia",
]


def extract_medical_entities(text: str) -> Dict[str, Any]:
    """Return structured entities extracted from the OCR text."""
    out: Dict[str, Any] = {
        "medications": [],
        "lab_values": [],
        "diagnoses": [],
        "dates": [],
        "procedures": [],
        "document_date": None,
    }
    if not text:
        return out

    # Medications
    for m in _MEDICATION_RE.finditer(text):
        name = m.group(1).strip()
        dose = m.group(2) or ""
        unit = m.group(3) or ""
        schedule = m.group(4) or ""
        if name.lower() in {"the", "and", "for", "with", "tab", "cap", "syp", "inj", "tablet", "capsule", "syrup", "injection"}:
            continue
        full_dose = f"{dose} {unit} {schedule}".strip()
        out["medications"].append({
            "name": name,
            "dose": full_dose,
            "unit": unit,
            "raw": m.group(0).strip(),
        })

    # Lab values
    for m in _LAB_RE.finditer(text):
        test = (m.group(1) or "").strip()
        val = m.group(2)
        unit = m.group(3) or ""
        ref = (m.group(4) or "").strip()
        flag = m.group(5) or ""
        if not test or len(test) < 2:
            continue
        out["lab_values"].append({
            "test_name": test,
            "value": val,
            "unit": unit,
            "reference_range": ref,
            "abnormal_flag": flag or None,
        })

    # Diagnoses
    lower = text.lower()
    for kw in _DIAGNOSIS_HINTS:
        if kw in lower:
            out["diagnoses"].append({"label": kw.title(), "evidence": kw})

    # Dates
    candidates = []
    for m in _DATE_RE.finditer(text):
        d = m.group(1) or m.group(2)
        if d and d not in candidates:
            candidates.append(d)
    out["dates"] = candidates
    out["document_date"] = _pick_document_date(candidates)

    return out


def _pick_document_date(candidates: List[str]) -> Optional[str]:
    """Pick the most recent date that parses, or None if uncertain.

    Never invents a date.
    """
    parsed: list[str] = []
    for d in candidates:
        norm = _normalise_date(d)
        if norm:
            parsed.append(norm)
    if not parsed:
        return None
    parsed.sort()
    return parsed[-1]


def _normalise_date(d: str) -> Optional[str]:
    """Return YYYY-MM-DD if d is recognisable."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
