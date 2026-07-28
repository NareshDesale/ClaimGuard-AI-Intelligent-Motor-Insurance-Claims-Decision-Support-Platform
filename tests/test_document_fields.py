from pathlib import Path
from typing import Any

import pytest

from src.documents import fields as fields_module


DOCUMENT_ID = "a" * 32


@pytest.fixture()
def extraction_result() -> dict[str, Any]:
    return {
        "claim_id": "CLM-TEST-001",
        "document_id": DOCUMENT_ID,
        "document_type": "claim_form",
        "pages": [
            {
                "page_number": 1,
                "text": "\n".join(
                    [
                        "Policy Number: POL-2026-7788",
                        "Claim No: CLM-2026-0001",
                        "Insured Name: Priya Shah",
                        "Customer Name: Priya S. Shah",
                        "Vehicle Registration Number: MH 12 AB 1234",
                        "Vehicle Make: Honda",
                        "Vehicle Model: City ZX",
                        "Chassis Number: MA3EUA61S00123456",
                        "Engine Number: ENG987654",
                        "Accident Date: 12/08/2026",
                        "Accident Time: 7:30 PM",
                        "Accident Location: MG Road, Pune",
                        "Policy Start Date: 01/01/2026",
                        "Policy Expiry Date: 31/12/2026",
                        "Invoice Number: INV-7788",
                        "Invoice Date: 14/08/2026",
                        "Claim Amount: INR 52,500.50",
                        "Repair Amount: Rs. 48,250",
                        "Garage Name: Sunrise Auto Works",
                        "Driving Licence Number: MH1420110012345",
                        "Driver Name: Rohan Shah",
                        "Police Report Number: FIR-2026-91",
                    ]
                ),
            }
        ],
    }


def test_extract_single_field_returns_found_metadata(
    extraction_result: dict[str, Any],
) -> None:
    result = fields_module.extract_single_field(
        pages=extraction_result["pages"],
        field_name="vehicle_registration_number",
    )

    assert result["status"] == "found"
    assert result["value"] == "MH12AB1234"
    assert result["raw_value"] == "MH 12 AB 1234"
    assert result["confidence"] > 0
    assert result["source_page"] == 1
    assert "Vehicle Registration Number" in result["evidence"]


def test_extract_structured_fields_covers_required_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    extraction_result: dict[str, Any],
) -> None:
    monkeypatch.setattr(
        fields_module,
        "FIELDS_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        fields_module,
        "load_saved_extraction_result",
        lambda claim_id, document_id: extraction_result,
    )

    result = fields_module.extract_structured_fields(
        claim_id="CLM-TEST-001",
        document_id=DOCUMENT_ID,
    )

    expected_fields = {
        "policy_number",
        "claim_number",
        "insured_name",
        "customer_name",
        "vehicle_registration_number",
        "vehicle_make",
        "vehicle_model",
        "chassis_number",
        "engine_number",
        "accident_date",
        "accident_time",
        "accident_location",
        "policy_start_date",
        "policy_expiry_date",
        "invoice_number",
        "invoice_date",
        "claim_amount",
        "repair_amount",
        "garage_name",
        "driving_licence_number",
        "driver_name",
        "police_report_number",
    }

    assert set(result["fields"]) == expected_fields
    assert result["total_supported_fields"] == len(expected_fields)
    assert result["missing_fields"] == []
    assert result["fields"]["accident_date"]["value"] == "2026-08-12"
    assert result["fields"]["accident_time"]["value"] == "19:30"
    assert result["fields"]["claim_amount"]["value"] == 52500.50
    assert result["fields"]["repair_amount"]["value"] == 48250.00

    output_path = tmp_path / "CLM-TEST-001" / f"{DOCUMENT_ID}.json"
    assert output_path.exists()


def test_missing_field_returns_not_found() -> None:
    result = fields_module.extract_single_field(
        pages=[
            {
                "page_number": 3,
                "text": "This document contains no invoice details.",
            }
        ],
        field_name="invoice_number",
    )

    assert result == {
        "status": "not_found",
        "value": None,
        "raw_value": None,
        "confidence": 0.0,
        "source_page": None,
        "evidence": None,
    }
