"""Standardised JSON response envelopes."""
from __future__ import annotations

from typing import Any, Optional


def ok(data: Any = None, message: str = "OK") -> dict:
    return {"success": True, "message": message, "data": data}


def fail(message: str, code: int = 400, data: Optional[Any] = None) -> dict:
    return {"success": False, "message": message, "data": data, "code": code}
