"""Convenience script: `python run.py` to start the dev server."""
from __future__ import annotations

import importlib
import importlib.util
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    pass

uvicorn = None
if importlib.util.find_spec("uvicorn") is not None:
    uvicorn = importlib.import_module("uvicorn")

if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn is not installed. Install the project dependencies first.")

    s = get_settings()
    uvicorn.run("app.main:app", host=s.app_host, port=s.app_port, reload=False, log_level="info")
