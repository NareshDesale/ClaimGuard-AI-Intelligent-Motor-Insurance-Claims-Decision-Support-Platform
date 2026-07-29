from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import (
    FastAPI,
    Request,
    Response,
)

from src.api.routers.assessment import router as assessment_router
from src.api.routers.claims import router as claims_router
from src.api.routers.documents import router as documents_router
from src.api.routers.fraud import router as fraud_router
from src.api.routers.health import router as health_router
from src.api.routers.rag import router as rag_router
from src.api.routers.reviews import router as reviews_router
from src.api.routers.validation import router as validation_router
from src.config import configure_logging
from src.database import init_database


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(
    application: FastAPI,
) -> AsyncIterator[None]:
    init_database()
    yield


def create_app() -> FastAPI:
    """Create and configure the ClaimGuard AI FastAPI application."""

    application = FastAPI(
        title="ClaimGuard AI API",
        description=(
            "Decision-support API for motor-insurance fraud risk "
            "prediction and policy-document question answering."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    application.include_router(health_router)
    application.include_router(fraud_router)
    application.include_router(claims_router)
    application.include_router(validation_router)
    application.include_router(assessment_router)
    application.include_router(reviews_router)
    application.include_router(rag_router)
    application.include_router(documents_router)

    @application.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: Any,
    ) -> Response:
        request_id = request.headers.get(
            "X-Request-ID",
            uuid4().hex,
        )
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_id=%s method=%s path=%s status_code=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
        )

        return response

    return application


app = create_app()
