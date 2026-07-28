from calendar import month_abbr
from datetime import date
from math import ceil
from typing import Any


MANUAL_FEATURE_REASON = (
    "This Oracle fraud-model feature is not reliably available "
    "from uploaded claim documents and should be supplied by a "
    "human reviewer or a trusted claim-administration system."
)


def parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None

    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def week_of_month(value: date) -> int:
    return int(
        ceil(value.day / 7)
    )


def days_between_category(
    start_date: date | None,
    end_date: date | None,
) -> str | None:
    if start_date is None or end_date is None:
        return None

    delta_days = (end_date - start_date).days

    if delta_days < 0:
        return "none"

    if delta_days <= 7:
        return "1 to 7"

    if delta_days <= 15:
        return "8 to 15"

    if delta_days <= 30:
        return "15 to 30"

    return "more than 30"


def first_found_field(
    documents: list[dict[str, Any]],
    field_name: str,
) -> Any:
    for document in documents:
        field_data = document.get("fields", {}).get(
            field_name,
            {},
        )

        if field_data.get("status") == "found":
            value = field_data.get("value")

            if value is not None:
                return value

    return None


def collect_available_claim_features(
    claim: dict[str, Any],
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Derive only model features that can be defensibly mapped from
    claim metadata or extracted document fields.
    """

    available_features: dict[str, Any] = {}

    accident_date = parse_iso_date(
        claim.get("accident_date")
        or first_found_field(documents, "accident_date")
    )
    reported_date = parse_iso_date(
        claim.get("reported_date")
    )
    policy_start_date = parse_iso_date(
        first_found_field(documents, "policy_start_date")
    )

    vehicle_make = first_found_field(
        documents,
        "vehicle_make",
    )

    if vehicle_make:
        available_features["Make"] = str(vehicle_make)

    if accident_date is not None:
        available_features["Month"] = month_abbr[
            accident_date.month
        ]
        available_features["WeekOfMonth"] = week_of_month(
            accident_date
        )
        available_features["DayOfWeek"] = accident_date.strftime(
            "%A"
        )
        available_features["Year"] = accident_date.year

    if reported_date is not None:
        available_features["MonthClaimed"] = month_abbr[
            reported_date.month
        ]
        available_features["WeekOfMonthClaimed"] = week_of_month(
            reported_date
        )
        available_features["DayOfWeekClaimed"] = (
            reported_date.strftime("%A")
        )

    days_policy_accident = days_between_category(
        policy_start_date,
        accident_date,
    )

    if days_policy_accident is not None:
        available_features["Days_Policy_Accident"] = (
            days_policy_accident
        )

    days_policy_claim = days_between_category(
        policy_start_date,
        reported_date,
    )

    if days_policy_claim is not None:
        available_features["Days_Policy_Claim"] = days_policy_claim

    police_report_number = first_found_field(
        documents,
        "police_report_number",
    )

    if police_report_number:
        available_features["PoliceReportFiled"] = "Yes"

    return available_features


def build_feature_mapping_report(
    expected_features: list[str],
    claim: dict[str, Any],
    documents: list[dict[str, Any]],
    manual_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manual_features = manual_features or {}

    available_features = collect_available_claim_features(
        claim=claim,
        documents=documents,
    )

    unknown_manual_features = sorted(
        feature
        for feature in manual_features
        if feature not in expected_features
    )

    manual_model_features = {
        feature: value
        for feature, value in manual_features.items()
        if feature in expected_features
    }

    features_used = {
        **available_features,
        **manual_model_features,
    }

    missing_features = [
        feature
        for feature in expected_features
        if feature not in features_used
    ]

    manually_required_features = [
        {
            "feature": feature,
            "reason": MANUAL_FEATURE_REASON,
        }
        for feature in missing_features
    ]

    warnings = [
        "Fraud risk is a decision-support signal, not proof of fraud.",
        (
            "Uploaded claim documents do not naturally contain all "
            "features expected by the trained Oracle fraud model."
        ),
    ]

    if unknown_manual_features:
        warnings.append(
            "Ignored unknown manual model features: "
            + ", ".join(unknown_manual_features)
        )

    return {
        "available_features": sorted(available_features.keys()),
        "missing_features": missing_features,
        "defaulted_features": [],
        "manually_required_features": manually_required_features,
        "features_used": features_used,
        "unknown_manual_features": unknown_manual_features,
        "warnings": warnings,
    }
