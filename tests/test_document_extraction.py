from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from src.documents import extraction as extraction_module
from src.documents.extraction import (
    clean_extracted_text,
    determine_overall_method,
    extract_image,
    run_ocr_on_image,
    save_extraction_result,
)


class FakeOCRReader:
    def readtext(
        self,
        image_array: np.ndarray,
        detail: int,
        paragraph: bool,
        decoder: str,
    ) -> list[tuple[object, str, float]]:
        assert image_array.ndim == 3
        assert detail == 1
        assert paragraph is False
        assert decoder == "greedy"

        return [
            (None, " Policy Number: POL-123 ", 0.92),
            (None, "", 0.50),
            (None, "Vehicle Number: MH12AB1234", 0.84),
        ]


def test_clean_extracted_text_normalizes_spacing() -> None:
    assert clean_extracted_text(
        "Claim\x00 Form\r\nPolicy   Number: POL-1\n\n\nEnd  \n"
    ) == "Claim Form\nPolicy Number: POL-1\n\nEnd"


def test_run_ocr_on_image_uses_mocked_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        extraction_module,
        "get_ocr_reader",
        lambda: FakeOCRReader(),
    )

    image_array = np.zeros(
        (4, 4, 3),
        dtype=np.uint8,
    )
    text, confidence = run_ocr_on_image(image_array)

    assert text == (
        "Policy Number: POL-123\n"
        "Vehicle Number: MH12AB1234"
    )
    assert confidence == 0.88


def test_extract_image_uses_ocr_without_real_easyocr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "claim.png"
    Image.new(
        "RGB",
        (8, 8),
        color="white",
    ).save(image_path)

    def fake_ocr(
        image_array: np.ndarray,
    ) -> tuple[str, float]:
        assert image_array.shape == (8, 8, 3)
        return (
            "Invoice Number: INV-1",
            0.88,
        )

    monkeypatch.setattr(
        extraction_module,
        "run_ocr_on_image",
        fake_ocr,
    )

    result = extract_image(image_path)

    assert result["page_count"] == 1
    assert result["pages"][0]["extraction_method"] == "ocr"
    assert result["pages"][0]["ocr_confidence"] == 0.88
    assert result["pages"][0]["text"] == "Invoice Number: INV-1"


def test_determine_overall_method_reports_hybrid() -> None:
    assert determine_overall_method(
        [
            {"extraction_method": "direct_text"},
            {"extraction_method": "ocr"},
        ]
    ) == "hybrid"


def test_save_extraction_result_writes_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        extraction_module,
        "EXTRACTION_ROOT",
        tmp_path,
    )

    result: dict[str, Any] = {
        "claim_id": "CLM-EX-001",
        "document_id": "a" * 32,
        "pages": [
            {
                "page_number": 1,
                "text": "Claim Form",
            }
        ],
    }

    output_path = save_extraction_result(
        claim_id="CLM-EX-001",
        document_id="a" * 32,
        result=result,
    )

    assert output_path == tmp_path / "CLM-EX-001" / f"{'a' * 32}.json"
    assert output_path.exists()
