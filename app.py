import logging
from typing import Any
from uuid import uuid4

from fastapi import (
    FastAPI,
    Request,
    Response,
)

from src.config import configure_logging
from src.api.routers.assessment import router as assessment_router
from src.api.routers.claims import router as claims_router
from src.api.routers.documents import router as documents_router
from src.api.routers.fraud import router as fraud_router
from src.api.routers.health import router as health_router
from src.api.routers.rag import router as rag_router
from src.api.routers.reviews import router as reviews_router
from src.api.routers.validation import router as validation_router
from src.database import (
    init_database,
)

# ---------------------------------------------------------
# Project paths and fraud model
# ---------------------------------------------------------

configure_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="ClaimGuard AI API",
    description=(
        "Decision-support API for motor-insurance fraud risk "
        "prediction and policy-document question answering."
    ),
    version="1.0.0",
)

app.include_router(health_router)
app.include_router(fraud_router)
app.include_router(claims_router)
app.include_router(validation_router)
app.include_router(assessment_router)
app.include_router(reviews_router)
app.include_router(rag_router)
app.include_router(documents_router)


@app.middleware("http")
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


@app.on_event("startup")
def startup() -> None:
    init_database()

