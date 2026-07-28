from pathlib import Path
from typing import Any

from src.risk.feature_mapping import (
    build_feature_mapping_report,
)
from src.risk.service import (
    run_claim_risk_assessment,
)


EXPECTED_FEATURES = [
    "Month",
    "WeekOfMonth",
    "DayOfWeek",
    "Make",
    "MonthClaimed",
    "WeekOfMonthClaimed",
    "DayOfWeekClaimed",
    "Days_Policy_Accident",
    "Days_Policy_Claim",
    "PoliceReportFiled",
    "Age",
]


class FakeModel:
    classes_ = [0, 1]

    def predict_proba(self, dataframe: Any) -> list[list[float]]:
        assert list(dataframe.columns) == EXPECTED_FEATURES
        return [[0.24, 0.76]]


def found(value: object) -> dict[str, object]:
    return {
        "status": "found",
        "value": value,
        "raw_value": str(value),
        "confidence": 0.9,
        "source_page": 1,
        "evidence": str(value),
    }


def documents() -> list[dict[str, object]]:
    return [
        {
            "document_id": "a" * 32,
            "document_type": "claim_form",
            "fields": {
                "vehicle_make": found("Honda"),
                "accident_date": found("2026-08-12"),
                "policy_start_date": found("2026-01-01"),
                "police_report_number": found("FIR-1"),
            },
        }
    ]


def claim() -> dict[str, object]:
    return {
        "claim_id": "CLM-RISK-001",
        "accident_date": "2026-08-12",
        "reported_date": "2026-08-14",
    }


def test_feature_mapping_reports_missing_manual_features() -> None:
    report = build_feature_mapping_report(
        expected_features=EXPECTED_FEATURES,
        claim=claim(),
        documents=documents(),
        manual_features={},
    )

    assert report["features_used"]["Month"] == "Aug"
    assert report["features_used"]["WeekOfMonth"] == 2
    assert report["features_used"]["Make"] == "Honda"
    assert report["features_used"]["PoliceReportFiled"] == "Yes"
    assert "Age" in report["missing_features"]
    assert report["defaulted_features"] == []


def test_risk_assessment_requires_missing_model_features() -> None:
    result = run_claim_risk_assessment(
        claim_id="CLM-RISK-001",
        claim=claim(),
        documents=documents(),
        manual_features={},
        expected_features=EXPECTED_FEATURES,
        model=FakeModel(),
        model_path=Path("missing-model.joblib"),
    )

    assert result["status"] == "manual_features_required"
    assert result["fraud_probability"] is None
    assert result["risk_level"] == "NOT_ASSESSED"
    assert "Age" in result["missing_features"]


def test_risk_assessment_runs_with_manual_features() -> None:
    result = run_claim_risk_assessment(
        claim_id="CLM-RISK-001",
        claim=claim(),
        documents=documents(),
        manual_features={
            "Age": 34,
        },
        expected_features=EXPECTED_FEATURES,
        model=FakeModel(),
        model_path=Path("missing-model.joblib"),
    )

    assert result["status"] == "assessed"
    assert result["fraud_probability"] == 0.76
    assert result["prediction"] == 1
    assert result["prediction_label"] == "Higher fraud-risk signal"
    assert result["risk_level"] == "HIGH"
    assert result["missing_features"] == []
