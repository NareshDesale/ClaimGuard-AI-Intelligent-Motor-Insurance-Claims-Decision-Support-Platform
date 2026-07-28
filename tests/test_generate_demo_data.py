from scripts.generate_demo_data import (
    build_scenarios,
    currency,
)


def test_build_scenarios_covers_required_demo_cases() -> None:
    scenarios = build_scenarios()
    scenario_ids = {
        scenario.scenario_id
        for scenario in scenarios
    }

    assert scenario_ids == {
        "01_complete_low_risk",
        "02_missing_document",
        "03_expired_policy",
        "04_vehicle_number_mismatch",
        "05_duplicate_invoice",
        "06_high_risk_claim",
        "07_ocr_image_claim",
    }


def test_demo_scenarios_use_synthetic_identifiers() -> None:
    for scenario in build_scenarios():
        assert scenario.claim["claim_id"].startswith("CLM-DEMO-")
        assert scenario.claim["policy_number"].startswith("POL-DEMO-")
        assert scenario.claim["customer_name"].startswith("Demo ")

        for document in scenario.documents:
            combined_text = "\n".join(document.lines)
            assert "SYNTHETIC" in combined_text
            assert "generated" in combined_text.lower()


def test_missing_document_scenario_omits_repair_invoice() -> None:
    scenario = next(
        item
        for item in build_scenarios()
        if item.scenario_id == "02_missing_document"
    )
    document_types = {
        document.document_type
        for document in scenario.documents
    }

    assert "repair_invoice" not in document_types


def test_ocr_image_scenario_has_png_claim_form() -> None:
    scenario = next(
        item
        for item in build_scenarios()
        if item.scenario_id == "07_ocr_image_claim"
    )
    claim_form = next(
        document
        for document in scenario.documents
        if document.document_type == "claim_form"
    )

    assert claim_form.output_format == "png"
    assert claim_form.filename.endswith(".png")


def test_currency_formats_amounts() -> None:
    assert currency(42500) == "INR 42,500.00"
