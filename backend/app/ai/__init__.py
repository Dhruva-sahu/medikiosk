"""AI-driven clinical intake engine.

Replaces the previous hardcoded question catalogue with a dynamic,
AI-powered clinical interview assistant.

Key changes from the previous version:
- Questions are generated dynamically by the AI provider
- The engine maintains conversation context and structured clinical data
- Red-flag detection works on free-form conversation answers
- Question count is enforced at 17 max with early-finish capability
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


MAX_QUESTIONS = 17


def detect_red_flags_from_conversation(
    conversation_history: List[Dict[str, str]],
    collected_data: Dict[str, Any],
) -> List[dict]:
    """Detect potentially urgent symptoms from free-form conversation answers.

    This replaces the previous keyword-matching system that required
    predefined question codes. Now it scans all patient answers for
    emergency indicators.

    The system is doing PRIORITISATION, not diagnosis. All messages are
    non-prescriptive, action-oriented and clearly request clinician review.
    """
    triggered: List[dict] = []

    # Gather all patient text
    patient_text = " ".join(
        e["content"] for e in conversation_history if e.get("role") == "patient"
    ).lower()

    # Also check chief complaint and collected data
    all_text = patient_text
    if collected_data.get("chief_complaint"):
        all_text += " " + collected_data["chief_complaint"].lower()

    # Emergency red-flag rules
    rules = [
        {
            "code": "CHEST_PAIN_WITH_BREATHING",
            "message": "Potentially urgent: chest discomfort with breathing difficulty. Please wait for immediate clinical assessment.",
            "severity": "HIGH",
            "requires": ["chest", "breath", "shortness", "dyspnea"],
        },
        {
            "code": "CHEST_PAIN_WITH_AUTONOMIC",
            "message": "Potentially urgent: chest discomfort with sweating or faintness. Please wait for immediate clinical assessment.",
            "severity": "HIGH",
            "requires": ["chest", "sweat", "diaphoresis", "faint", "dizz"],
        },
        {
            "code": "NEURO_EMERGENCY",
            "message": "Potentially urgent: sudden neurological symptoms (facial droop, slurred speech, one-sided weakness). Please wait for immediate clinical assessment.",
            "severity": "HIGH",
            "requires": ["stroke", "facial droop", "slurred", "one-sided weakness"],
        },
        {
            "code": "SEVERE_BLEEDING",
            "message": "Potentially urgent: severe or uncontrolled bleeding reported. Please wait for immediate clinical assessment.",
            "severity": "HIGH",
            "requires": ["blood vomiting", "vomiting blood", "uncontrolled bleeding", "severe bleeding"],
        },
        {
            "code": "ALTERED_CONSCIOUSNESS",
            "message": "Potentially urgent: altered consciousness or seizure reported. Please wait for immediate clinical assessment.",
            "severity": "HIGH",
            "requires": ["unconscious", "loss of consciousness", "seizure", "convulsion"],
        },
        {
            "code": "BREATHLESSNESS_ALONE",
            "message": "Breathlessness reported. Clinician review will be prioritised.",
            "severity": "MEDIUM",
            "requires": ["breathless", "dyspnea", "shortness of breath", "can't breathe"],
        },
    ]

    seen_codes = set()

    for rule in rules:
        keywords = rule["requires"]
        if any(kw in all_text for kw in keywords):
            # For chest pain rules, ensure both conditions are met
            if rule["code"] == "CHEST_PAIN_WITH_BREATHING" and not ("chest" in all_text and any(k in all_text for k in ["breath", "shortness", "dyspnea"])):
                continue
            if rule["code"] == "CHEST_PAIN_WITH_AUTONOMIC" and not ("chest" in all_text and any(k in all_text for k in ["sweat", "diaphoresis", "faint", "dizz"])):
                continue

            if rule["code"] not in seen_codes:
                triggered.append({
                    "code": rule["code"],
                    "message": rule["message"],
                    "severity": rule["severity"],
                    "triggered_by": ["conversation"],
                })
                seen_codes.add(rule["code"])

    # High severity pain detection
    import re
    nums = re.findall(r'\b(\d+)\b', patient_text)
    for n in nums:
        try:
            val = int(n)
            if val >= 9:
                if "HIGH_SEVERITY_PAIN" not in seen_codes:
                    triggered.append({
                        "code": "HIGH_SEVERITY_PAIN",
                        "message": "Pain reported as very severe (9-10/10). Clinician review will be prioritised.",
                        "severity": "MEDIUM",
                        "triggered_by": ["conversation"],
                    })
                    seen_codes.add("HIGH_SEVERITY_PAIN")
                break
        except ValueError:
            pass

    return triggered


def structured_from_conversation(
    conversation_history: List[Dict[str, str]],
    collected_data: Dict[str, Any],
    chief_complaint: Optional[str] = None,
) -> Dict[str, Any]:
    """Build structured clinical data from the AI-driven conversation.

    This merges the AI-extracted clinical_data with the conversation
    history to produce the structured format expected by the summary generator.
    """
    out: Dict[str, Any] = {
        "chief_complaint": chief_complaint or collected_data.get("chief_complaint", ""),
        "hpi": {},
        "past_medical_history": [],
        "past_surgical_history": [],
        "drug_history": [],
        "current_medications": [],
        "allergies": [],
        "family_history": [],
        "personal_history": {},
        "review_of_systems": {},
        "ayush": {},
    }

    # Map collected_data keys to structured format
    key_mapping = {
        "duration": ("hpi", "duration"),
        "onset": ("hpi", "onset"),
        "location": ("hpi", "location"),
        "severity": ("hpi", "severity"),
        "character": ("hpi", "character"),
        "associated_symptoms": ("hpi", "associated_symptoms"),
        "aggravating_factors": ("hpi", "aggravating_factors"),
        "relieving_factors": ("hpi", "relieving_factors"),
        "timing": ("hpi", "timing"),
        "radiation": ("hpi", "radiation"),
        "past_medical_history": ("past_medical_history", None),
        "past_surgical_history": ("past_surgical_history", None),
        "medications": ("current_medications", None),
        "drug_history": ("drug_history", None),
        "allergies": ("allergies", None),
        "family_history": ("family_history", None),
        "personal_history": ("personal_history", None),
        "review_of_systems": ("review_of_systems", None),
        "smoking": ("personal_history", "smoking"),
        "alcohol": ("personal_history", "alcohol"),
    }

    for key, value in collected_data.items():
        if key == "chief_complaint":
            out["chief_complaint"] = value
            continue
        if key in key_mapping:
            section, subkey = key_mapping[key]
            if subkey:
                if isinstance(out.get(section), dict):
                    out[section][subkey] = value
                elif isinstance(out.get(section), list):
                    pass  # Don't overwrite list with scalar
            elif isinstance(out.get(section), list):
                if isinstance(value, str) and value:
                    out[section].append(value)
                elif isinstance(value, list):
                    out[section].extend(value)

    return out
