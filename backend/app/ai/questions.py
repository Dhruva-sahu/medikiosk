"""Curated list of clinically relevant questions seeded at startup."""
from __future__ import annotations

from typing import List

from app.ai import AYUSH_DASHAVIDHA, CHIEF_COMPLAINT, SOCRATES, STANDARD_HISTORY, get_intake_curriculum


def build_question_rows() -> List[dict]:
    rows: List[dict] = []
    for q in get_intake_curriculum("STANDARD"):
        rows.append({
            "code": q.code,
            "domain": q.domain,
            "prompt_en": q.prompt_en,
            "prompt_hi": q.prompt_hi,
            "answer_type": q.answer_type,
            "options_json": None,
            "required": q.required,
            "priority": q.priority,
        })
    # AYUSH extras
    for q in AYUSH_DASHAVIDHA:
        if any(r["code"] == q.code for r in rows):
            continue
        rows.append({
            "code": q.code,
            "domain": q.domain,
            "prompt_en": q.prompt_en,
            "prompt_hi": q.prompt_hi,
            "answer_type": q.answer_type,
            "options_json": None,
            "required": q.required,
            "priority": q.priority,
        })
    return rows
