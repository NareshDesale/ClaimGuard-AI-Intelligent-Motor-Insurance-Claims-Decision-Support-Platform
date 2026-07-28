from types import SimpleNamespace

import pytest

from src.documents.service import (
    sanitize_filename,
    validate_file_signature,
    validate_pdf_file,
    validate_upload,
)


def test_sanitize_filename_removes_path_and_unsafe_characters() -> None:
    assert sanitize_filename("../Aadhaar*Card?.pdf") == (
        "Aadhaar_Card_.pdf"
    )


def test_validate_upload_rejects_extension_content_type_mismatch() -> None:
    upload = SimpleNamespace(
        filename="invoice.pdf",
        content_type="image/png",
    )

    with pytest.raises(ValueError, match="do not match"):
        validate_upload(upload)


def test_validate_upload_requires_content_type() -> None:
    upload = SimpleNamespace(
        filename="invoice.pdf",
        content_type=None,
    )

    with pytest.raises(ValueError, match="content type"):
        validate_upload(upload)


def test_validate_file_signature_accepts_pdf_signature() -> None:
    validate_file_signature(
        extension=".pdf",
        first_bytes=b"%PDF-1.7\n",
    )


def test_validate_file_signature_rejects_fake_pdf() -> None:
    with pytest.raises(ValueError, match="PDF signature"):
        validate_file_signature(
            extension=".pdf",
            first_bytes=b"not a pdf",
        )


def test_validate_file_signature_accepts_png_signature() -> None:
    validate_file_signature(
        extension=".png",
        first_bytes=b"\x89PNG\r\n\x1a\nextra",
    )


def test_validate_file_signature_accepts_jpeg_signature() -> None:
    validate_file_signature(
        extension=".jpg",
        first_bytes=b"\xff\xd8\xff\xe0extra",
    )


def test_validate_pdf_file_wraps_parser_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_open(_path: object) -> object:
        raise RuntimeError("broken pdf")

    monkeypatch.setattr(
        "src.documents.service.fitz.open",
        broken_open,
    )

    with pytest.raises(ValueError, match="could not be opened"):
        validate_pdf_file(
            SimpleNamespace()
        )
