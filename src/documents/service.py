import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz  # PyMuPDF
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from src.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"

SETTINGS = get_settings()

MAX_FILE_SIZE = SETTINGS.max_upload_size_bytes
WRITE_CHUNK_SIZE = 1024 * 1024  # 1 MB
MAX_PDF_PAGES = 50
MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGE_WIDTH = 8000
MAX_IMAGE_HEIGHT = 8000
SIGNATURE_READ_BYTES = 16

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
}

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
}

EXTENSION_CONTENT_TYPES = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
}

ALLOWED_DOCUMENT_TYPES = {
    "claim_form",
    "policy_document",
    "repair_invoice",
    "accident_report",
    "identity_document",
    "vehicle_image",
    "other",
}


def sanitize_filename(filename: str) -> str:
    """
    Keep an audit-friendly original filename without trusting paths.
    """

    filename_only = Path(filename).name.strip()

    if not filename_only:
        raise ValueError(
            "Uploaded file must have a valid filename."
        )

    sanitized = re.sub(
        r"[^A-Za-z0-9._ -]",
        "_",
        filename_only,
    )
    sanitized = re.sub(
        r"\s+",
        " ",
        sanitized,
    ).strip(" .")

    if not sanitized:
        raise ValueError(
            "Uploaded filename does not contain usable characters."
        )

    return sanitized[:180]


def validate_claim_id(claim_id: str) -> str:
    """
    Validate a claim ID before using it as a folder name.
    """

    cleaned_claim_id = claim_id.strip()

    if not re.fullmatch(
        r"[A-Za-z0-9_-]{3,50}",
        cleaned_claim_id,
    ):
        raise ValueError(
            "claim_id must contain 3-50 letters, numbers, "
            "underscores or hyphens."
        )

    return cleaned_claim_id


def validate_document_type(
    document_type: str,
) -> str:
    """
    Validate the business document category.
    """

    cleaned_type = document_type.strip().lower()

    if cleaned_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError(
            "Invalid document_type. Allowed values are: "
            + ", ".join(sorted(ALLOWED_DOCUMENT_TYPES))
        )

    return cleaned_type


def validate_upload(
    upload: UploadFile,
) -> tuple[str, str]:
    """
    Validate filename extension and content type.
    """

    if not upload.filename:
        raise ValueError(
            "Uploaded file must have a filename."
        )

    original_filename = sanitize_filename(
        upload.filename
    )

    extension = Path(
        original_filename
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file extension. Allowed extensions: "
            + ", ".join(sorted(ALLOWED_EXTENSIONS))
        )

    if not upload.content_type:
        raise ValueError(
            "Uploaded file must include a content type."
        )

    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(
            "Unsupported file content type: "
            f"{upload.content_type}"
        )

    expected_content_types = EXTENSION_CONTENT_TYPES[extension]

    if upload.content_type not in expected_content_types:
        raise ValueError(
            "File extension and content type do not match. "
            f"Extension '{extension}' expects: "
            + ", ".join(sorted(expected_content_types))
        )

    return original_filename, extension


def validate_file_signature(
    extension: str,
    first_bytes: bytes,
) -> None:
    """
    Verify the file signature before accepting stored content.
    """

    if extension == ".pdf":
        if not first_bytes.startswith(b"%PDF-"):
            raise ValueError(
                "Uploaded PDF does not have a valid PDF signature."
            )

        return

    if extension == ".png":
        if not first_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(
                "Uploaded PNG does not have a valid PNG signature."
            )

        return

    if extension in {".jpg", ".jpeg"}:
        if not first_bytes.startswith(b"\xff\xd8\xff"):
            raise ValueError(
                "Uploaded JPEG does not have a valid JPEG signature."
            )

        return

    raise ValueError(
        f"Unsupported file extension: {extension}"
    )


def validate_pdf_file(
    path: Path,
) -> int:
    """
    Open a PDF and enforce the page-count limit.
    """

    try:
        with fitz.open(path) as pdf_document:
            page_count = len(pdf_document)

            if page_count == 0:
                raise ValueError(
                    "Uploaded PDF contains no pages."
                )

            if page_count > MAX_PDF_PAGES:
                raise ValueError(
                    "Uploaded PDF exceeds the maximum allowed "
                    f"page count of {MAX_PDF_PAGES}."
                )

            return page_count

    except ValueError:
        raise
    except Exception as error:
        raise ValueError(
            f"Uploaded PDF could not be opened: {error}"
        ) from error


def validate_image_file(
    path: Path,
) -> tuple[int, int]:
    """
    Decode an image and enforce dimension limits.
    """

    try:
        with Image.open(path) as image:
            image.verify()

        with Image.open(path) as image:
            width, height = image.size

    except (OSError, UnidentifiedImageError) as error:
        raise ValueError(
            "Uploaded image could not be decoded."
        ) from error

    if width <= 0 or height <= 0:
        raise ValueError(
            "Uploaded image has invalid dimensions."
        )

    if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
        raise ValueError(
            "Uploaded image dimensions exceed the maximum allowed "
            f"size of {MAX_IMAGE_WIDTH}x{MAX_IMAGE_HEIGHT}."
        )

    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(
            "Uploaded image exceeds the maximum allowed pixel count."
        )

    return width, height


def validate_stored_file(
    path: Path,
    extension: str,
    first_bytes: bytes,
) -> dict[str, Any]:
    """
    Run content validation after streaming the file to disk.
    """

    validate_file_signature(
        extension=extension,
        first_bytes=first_bytes,
    )

    if extension == ".pdf":
        return {
            "page_count": validate_pdf_file(path),
        }

    width, height = validate_image_file(path)

    return {
        "image_width": width,
        "image_height": height,
    }


async def save_claim_document(
    claim_id: str,
    document_type: str,
    upload: UploadFile,
) -> dict[str, Any]:
    """
    Validate and store an uploaded claim document.
    """

    cleaned_claim_id = validate_claim_id(
        claim_id
    )

    cleaned_document_type = validate_document_type(
        document_type
    )

    original_filename, extension = validate_upload(
        upload
    )

    document_id = uuid4().hex

    claim_directory = (
        UPLOAD_ROOT
        / cleaned_claim_id
    )

    claim_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    stored_filename = (
        f"{document_id}_{cleaned_document_type}"
        f"{extension}"
    )

    destination_path = (
        claim_directory
        / stored_filename
    )

    total_size = 0
    first_bytes = b""

    try:
        with destination_path.open("wb") as output_file:
            while True:
                chunk = await upload.read(
                    WRITE_CHUNK_SIZE
                )

                if not chunk:
                    break

                total_size += len(chunk)

                if len(first_bytes) < SIGNATURE_READ_BYTES:
                    remaining_signature_bytes = (
                        SIGNATURE_READ_BYTES
                        - len(first_bytes)
                    )
                    first_bytes += chunk[:remaining_signature_bytes]

                if total_size > MAX_FILE_SIZE:
                    raise ValueError(
                        "File exceeds the maximum "
                        "allowed size of 10 MB."
                    )

                output_file.write(chunk)

        if total_size == 0:
            raise ValueError(
                "Uploaded file is empty."
            )

        validation_metadata = validate_stored_file(
            path=destination_path,
            extension=extension,
            first_bytes=first_bytes,
        )

    except Exception:
        if destination_path.exists():
            destination_path.unlink()

        raise

    finally:
        await upload.close()

    relative_path = destination_path.relative_to(
        PROJECT_ROOT
    )

    return {
        "document_id": document_id,
        "claim_id": cleaned_claim_id,
        "document_type": cleaned_document_type,
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "content_type": upload.content_type,
        "size_bytes": total_size,
        "storage_path": str(relative_path),
        "status": "uploaded",
        "validation": validation_metadata,
    }
