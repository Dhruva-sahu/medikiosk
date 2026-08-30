"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth as auth_api
from app.api import clinician as clinician_api
from app.api import consent as consent_api
from app.api import documents as documents_api
from app.api import intake as intake_api
from app.api import integrations as integrations_api
from app.api import speech as speech_api
from app.api import system as system_api
from app.config import get_settings
from app.db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Swasthya Setu ready")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    app = FastAPI(
        title="Swasthya Setu API",
        description=(
            "Swasthya Setu — AI-Powered Clinical History & Patient Case-Taking Platform. "
            "Backend for patient kiosk intake, document OCR, clinical summarisation "
            "and clinician verification. "
            "AI prepares the case. The clinician makes the decision."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api/v1"
    app.include_router(system_api.router, prefix=api_prefix)
    app.include_router(auth_api.router, prefix=api_prefix)
    app.include_router(consent_api.router, prefix=api_prefix)
    app.include_router(intake_api.router, prefix=api_prefix)
    app.include_router(documents_api.router, prefix=api_prefix)
    app.include_router(speech_api.router, prefix=api_prefix)
    app.include_router(clinician_api.router, prefix=api_prefix)
    app.include_router(integrations_api.router, prefix=api_prefix)

    @app.exception_handler(Exception)
    async def unhandled(request, exc):  # noqa: ARG001
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Something went wrong. Please try again.", "data": None},
        )

    return app


app = create_app()
