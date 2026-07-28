from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from src.claims.repository import (
    create_document,
    get_or_create_claim,
    mark_document_extracted,
    save_field_results,
)
from src.database import get_db
from src.documents.extraction import (
    extract_document_text,
    load_extraction_result,
)
from src.documents.fields import (
    extract_structured_fields,
    load_field_result,
)
from src.documents.service import (
    ALLOWED_DOCUMENT_TYPES,
    save_claim_document,
)


router = APIRouter(tags=["documents"])


@router.get("/documents/types")
def get_document_types() -> dict[str, Any]:
    """Return supported insurance-document categories."""

    return {
        "document_types": sorted(
            ALLOWED_DOCUMENT_TYPES,
        ),
    }


@router.post("/claims/{claim_id}/documents")
async def upload_claim_document(
    claim_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload a PDF or image associated with a claim."""

    try:
        upload_result = await save_claim_document(
            claim_id=claim_id,
            document_type=document_type,
            upload=file,
        )

        get_or_create_claim(
            db=db,
            claim_id=upload_result["claim_id"],
        )
        create_document(
            db=db,
            document_data=upload_result,
        )

        return upload_result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "The document could not be stored: "
                f"{error}"
            ),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Document upload failed: "
                f"{error}"
            ),
        ) from error


@router.post(
    "/claims/{claim_id}/documents/"
    "{document_id}/extract"
)
def extract_uploaded_document(
    claim_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Extract text from an uploaded PDF or image."""

    try:
        result = extract_document_text(
            claim_id=claim_id,
            document_id=document_id,
        )

        mark_document_extracted(
            db=db,
            claim_id=claim_id,
            document_id=document_id,
        )

        return result

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Document text extraction failed: "
                f"{error}"
            ),
        ) from error


@router.get(
    "/claims/{claim_id}/documents/"
    "{document_id}/extraction"
)
def get_document_extraction(
    claim_id: str,
    document_id: str,
) -> dict[str, Any]:
    """Return a previously saved extraction result."""

    try:
        return load_extraction_result(
            claim_id=claim_id,
            document_id=document_id,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not load extraction result: "
                f"{error}"
            ),
        ) from error


@router.post(
    "/claims/{claim_id}/documents/"
    "{document_id}/fields"
)
def extract_document_fields(
    claim_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Extract structured insurance fields from saved document text."""

    try:
        result = extract_structured_fields(
            claim_id=claim_id,
            document_id=document_id,
        )

        save_field_results(
            db=db,
            claim_id=claim_id,
            document_id=document_id,
            fields=result["fields"],
        )

        return result

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Structured field extraction failed: "
                f"{error}"
            ),
        ) from error


@router.get(
    "/claims/{claim_id}/documents/"
    "{document_id}/fields"
)
def get_document_fields(
    claim_id: str,
    document_id: str,
) -> dict[str, Any]:
    """Return previously saved structured fields."""

    try:
        return load_field_result(
            claim_id=claim_id,
            document_id=document_id,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
