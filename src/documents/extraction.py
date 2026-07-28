import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, UnidentifiedImageError

from src.config import get_settings
from src.documents.service import (
    PROJECT_ROOT,
    UPLOAD_ROOT,
    validate_claim_id,
)


EXTRACTION_ROOT = PROJECT_ROOT / "data" / "extracted"

SUPPORTED_PDF_EXTENSION = ".pdf"

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
}

# When direct PDF extraction returns fewer characters than this,
# OCR is used for that page.
MINIMUM_DIRECT_TEXT_CHARACTERS = 80

# Higher DPI can improve OCR but increases processing time.
PDF_OCR_DPI = 200

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_ocr_reader() -> Any:
    """
    Load the OCR model once and reuse it for future requests.

    gpu=False is used because the project currently targets
    normal CPU execution.
    """

    settings = get_settings()

    if not settings.ocr_enabled:
        raise RuntimeError(
            "OCR is disabled by OCR_ENABLED=false."
        )

    logger.info(
        "Loading EasyOCR model for languages: %s",
        ",".join(settings.ocr_language_list),
    )

    try:
        import easyocr
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "EasyOCR is not installed. Install project OCR "
            "dependencies or set OCR_ENABLED=false for non-OCR "
            "workflows."
        ) from error

    return easyocr.Reader(
        settings.ocr_language_list,
        gpu=False,
    )


def validate_document_id(document_id: str) -> str:
    """
    Validate the UUID-style document ID created during upload.
    """

    cleaned_document_id = document_id.strip().lower()

    if not re.fullmatch(
        r"[a-f0-9]{32}",
        cleaned_document_id,
    ):
        raise ValueError(
            "document_id must be a valid 32-character "
            "hexadecimal identifier."
        )

    return cleaned_document_id


def find_uploaded_document(
    claim_id: str,
    document_id: str,
) -> Path:
    """
    Find an uploaded file using the claim ID and document ID.
    """

    cleaned_claim_id = validate_claim_id(
        claim_id
    )

    cleaned_document_id = validate_document_id(
        document_id
    )

    claim_directory = (
        UPLOAD_ROOT
        / cleaned_claim_id
    )

    if not claim_directory.exists():
        raise FileNotFoundError(
            f"No uploaded documents were found for "
            f"claim '{cleaned_claim_id}'."
        )

    matching_files = list(
        claim_directory.glob(
            f"{cleaned_document_id}_*"
        )
    )

    if not matching_files:
        raise FileNotFoundError(
            f"Document '{cleaned_document_id}' was not found "
            f"for claim '{cleaned_claim_id}'."
        )

    if len(matching_files) > 1:
        raise RuntimeError(
            "Multiple uploaded files were found for the same "
            "document ID."
        )

    return matching_files[0]


def count_meaningful_characters(text: str) -> int:
    """
    Count characters after removing whitespace.
    """

    return len(
        re.sub(
            r"\s+",
            "",
            text,
        )
    )


def clean_extracted_text(text: str) -> str:
    """
    Normalize extracted text without removing line structure.
    """

    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r" +\n",
        "\n",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def run_ocr_on_image(
    image_array: np.ndarray,
) -> tuple[str, float | None]:
    """
    Run EasyOCR on an image and return text and average confidence.
    """

    reader = get_ocr_reader()

    results = reader.readtext(
        image_array,
        detail=1,
        paragraph=False,
        decoder="greedy",
    )

    extracted_lines: list[str] = []
    confidence_scores: list[float] = []

    for result in results:
        if len(result) < 3:
            continue

        _, detected_text, confidence = result

        cleaned_line = str(
            detected_text
        ).strip()

        if not cleaned_line:
            continue

        extracted_lines.append(
            cleaned_line
        )

        confidence_scores.append(
            float(confidence)
        )

    extracted_text = "\n".join(
        extracted_lines
    )

    average_confidence: float | None = None

    if confidence_scores:
        average_confidence = round(
            sum(confidence_scores)
            / len(confidence_scores),
            4,
        )

    return (
        clean_extracted_text(extracted_text),
        average_confidence,
    )


def convert_pdf_page_to_image(
    page: fitz.Page,
) -> np.ndarray:
    """
    Render a PDF page as an RGB NumPy image for OCR.
    """

    pixmap = page.get_pixmap(
        dpi=PDF_OCR_DPI,
        colorspace=fitz.csRGB,
        alpha=False,
    )

    image_array = np.frombuffer(
        pixmap.samples,
        dtype=np.uint8,
    ).reshape(
        pixmap.height,
        pixmap.width,
        3,
    )

    return image_array.copy()


def extract_pdf(
    document_path: Path,
) -> dict[str, Any]:
    """
    Extract text from every PDF page.

    Direct text extraction is used first. OCR is used only when
    the page has little or no selectable text.
    """

    pages: list[dict[str, Any]] = []

    try:
        with fitz.open(
            document_path
        ) as pdf_document:

            total_pages = len(
                pdf_document
            )

            for page_index in range(
                total_pages
            ):
                page = pdf_document.load_page(
                    page_index
                )

                page_number = page_index + 1

                direct_text = clean_extracted_text(
                    page.get_text(
                        "text",
                        sort=True,
                    )
                )

                direct_character_count = (
                    count_meaningful_characters(
                        direct_text
                    )
                )

                if (
                    direct_character_count
                    >= MINIMUM_DIRECT_TEXT_CHARACTERS
                ):
                    pages.append(
                        {
                            "page_number": page_number,
                            "extraction_method": (
                                "direct_text"
                            ),
                            "ocr_confidence": None,
                            "character_count": len(
                                direct_text
                            ),
                            "text": direct_text,
                        }
                    )

                    continue

                page_image = (
                    convert_pdf_page_to_image(
                        page
                    )
                )

                ocr_text, confidence = (
                    run_ocr_on_image(
                        page_image
                    )
                )

                # Keep direct text when OCR cannot detect anything.
                if not ocr_text and direct_text:
                    final_text = direct_text
                    extraction_method = (
                        "direct_text_fallback"
                    )
                    confidence = None
                else:
                    final_text = ocr_text
                    extraction_method = "ocr"

                pages.append(
                    {
                        "page_number": page_number,
                        "extraction_method": (
                            extraction_method
                        ),
                        "ocr_confidence": confidence,
                        "character_count": len(
                            final_text
                        ),
                        "text": final_text,
                    }
                )

    except fitz.FileDataError as error:
        raise ValueError(
            f"Invalid or damaged PDF file: {error}"
        ) from error

    return {
        "page_count": len(pages),
        "pages": pages,
    }


def extract_image(
    document_path: Path,
) -> dict[str, Any]:
    """
    Extract text from a PNG or JPEG image.
    """

    try:
        with Image.open(
            document_path
        ) as image:

            rgb_image = image.convert(
                "RGB"
            )

            image_array = np.asarray(
                rgb_image
            )

    except UnidentifiedImageError as error:
        raise ValueError(
            "The uploaded image could not be opened."
        ) from error

    ocr_text, confidence = run_ocr_on_image(
        image_array
    )

    return {
        "page_count": 1,
        "pages": [
            {
                "page_number": 1,
                "extraction_method": "ocr",
                "ocr_confidence": confidence,
                "character_count": len(
                    ocr_text
                ),
                "text": ocr_text,
            }
        ],
    }


def determine_overall_method(
    pages: list[dict[str, Any]],
) -> str:
    """
    Determine whether extraction was direct, OCR or hybrid.
    """

    methods = {
        page["extraction_method"]
        for page in pages
    }

    if methods == {"direct_text"}:
        return "direct_text"

    if methods == {"ocr"}:
        return "ocr"

    return "hybrid"


def infer_document_type(
    document_path: Path,
    document_id: str,
) -> str:
    """
    Extract document type from the stored filename.

    Stored filename format:
    document_id_document_type.extension
    """

    filename_without_extension = (
        document_path.stem
    )

    prefix = f"{document_id}_"

    if filename_without_extension.startswith(
        prefix
    ):
        return filename_without_extension[
            len(prefix):
        ]

    return "unknown"


def save_extraction_result(
    claim_id: str,
    document_id: str,
    result: dict[str, Any],
) -> Path:
    """
    Save extracted text and metadata as JSON.
    """

    output_directory = (
        EXTRACTION_ROOT
        / claim_id
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_directory
        / f"{document_id}.json"
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            result,
            output_file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path


def extract_document_text(
    claim_id: str,
    document_id: str,
) -> dict[str, Any]:
    """
    Run text extraction for an uploaded PDF or image.
    """

    cleaned_claim_id = validate_claim_id(
        claim_id
    )

    cleaned_document_id = validate_document_id(
        document_id
    )

    document_path = find_uploaded_document(
        cleaned_claim_id,
        cleaned_document_id,
    )

    extension = (
        document_path.suffix.lower()
    )

    if extension == SUPPORTED_PDF_EXTENSION:
        extraction_data = extract_pdf(
            document_path
        )

    elif extension in SUPPORTED_IMAGE_EXTENSIONS:
        extraction_data = extract_image(
            document_path
        )

    else:
        raise ValueError(
            f"Text extraction is not supported for "
            f"'{extension}' files."
        )

    pages = extraction_data["pages"]

    complete_text = "\n\n".join(
        page["text"]
        for page in pages
        if page["text"]
    )

    result: dict[str, Any] = {
        "claim_id": cleaned_claim_id,
        "document_id": cleaned_document_id,
        "document_type": infer_document_type(
            document_path,
            cleaned_document_id,
        ),
        "original_stored_filename": (
            document_path.name
        ),
        "file_extension": extension,
        "status": "extracted",
        "overall_extraction_method": (
            determine_overall_method(
                pages
            )
        ),
        "page_count": extraction_data[
            "page_count"
        ],
        "character_count": len(
            complete_text
        ),
        "complete_text": complete_text,
        "pages": pages,
    }

    output_path = save_extraction_result(
        claim_id=cleaned_claim_id,
        document_id=cleaned_document_id,
        result=result,
    )

    result["extraction_result_path"] = str(
        output_path.relative_to(
            PROJECT_ROOT
        )
    )

    return result


def load_extraction_result(
    claim_id: str,
    document_id: str,
) -> dict[str, Any]:
    """
    Load a previously saved extraction result.
    """

    cleaned_claim_id = validate_claim_id(
        claim_id
    )

    cleaned_document_id = validate_document_id(
        document_id
    )

    result_path = (
        EXTRACTION_ROOT
        / cleaned_claim_id
        / f"{cleaned_document_id}.json"
    )

    if not result_path.exists():
        raise FileNotFoundError(
            "No saved extraction result was found for "
            "this document."
        )

    with result_path.open(
        "r",
        encoding="utf-8",
    ) as result_file:
        return json.load(
            result_file
        )
