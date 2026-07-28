import json
import re
from pathlib import Path
from typing import Any, Callable

from dateutil import parser as date_parser

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIELDS_ROOT = PROJECT_ROOT / "data" / "fields"

DATE_PATTERN = (
    r"\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}|"
    r"\d{4}[./\-]\d{1,2}[./\-]\d{1,2}|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}"
)

TIME_PATTERN = (
    r"\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?|"
    r"\d{1,2}\s*(?:AM|PM|am|pm)"
)


def normalize_whitespace(value: str) -> str:
    """Remove unnecessary whitespace from a captured value."""

    return re.sub(r"\s+", " ", value).strip(" :-|")


def validate_claim_id(claim_id: str) -> str:
    """Validate a claim ID before using it as a folder name."""

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


def validate_document_id(document_id: str) -> str:
    """
    Validate the UUID-style document ID created during upload.

    Kept local to avoid importing OCR/PDF dependencies when only
    structured-field parsing is being tested.
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


def normalize_uppercase(value: str) -> str:
    return normalize_whitespace(value).upper()


def normalize_registration_number(value: str) -> str:
    return re.sub(r"[\s\-]+", "", normalize_uppercase(value))


def normalize_amount(value: str) -> float:
    """
    Convert values such as INR 25,500.50 or Rs. 25,500
    into a numeric amount.
    """

    value_without_currency = re.sub(
        r"(?i)\b(?:rs|inr)\.?\s*",
        "",
        value,
    )

    cleaned_value = re.sub(
        r"[^\d.]",
        "",
        value_without_currency,
    )

    if not cleaned_value:
        raise ValueError(
            f"Could not convert '{value}' into an amount."
        )

    return round(float(cleaned_value), 2)


def normalize_date(value: str) -> str:
    """
    Convert common Indian document dates into YYYY-MM-DD.

    Day-first parsing is used for dates such as 12/08/2026.
    """

    cleaned_value = normalize_whitespace(value)

    parsed_date = date_parser.parse(
        cleaned_value,
        dayfirst=True,
        fuzzy=True,
    )

    return parsed_date.date().isoformat()


def normalize_time(value: str) -> str:
    """Convert common claim times into HH:MM format when possible."""

    cleaned_value = normalize_whitespace(value).upper()

    match = re.fullmatch(
        r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?",
        cleaned_value,
    )

    if not match:
        return cleaned_value

    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    meridiem = match.group(3)

    if meridiem == "PM" and hour != 12:
        hour += 12

    if meridiem == "AM" and hour == 12:
        hour = 0

    if hour > 23 or minute > 59:
        return cleaned_value

    return f"{hour:02d}:{minute:02d}"


FIELD_PATTERNS: dict[str, list[str]] = {
    "policy_number": [
        (
            r"(?:policy\s*(?:number|no\.?|#))"
            r"\s*[:\-]?\s*"
            r"([A-Z0-9][A-Z0-9/\-]{4,39})"
        ),
    ],
    "claim_number": [
        (
            r"(?:claim\s*(?:number|no\.?|#))"
            r"\s*[:\-]?\s*"
            r"([A-Z0-9][A-Z0-9/\-]{4,39})"
        ),
    ],
    "insured_name": [
        (
            r"(?:name\s+of\s+(?:the\s+)?insured|"
            r"insured\s*(?:name)?|"
            r"policyholder\s*name)"
            r"\s*[:\-]?\s*"
            r"([A-Za-z][A-Za-z .'\-]{2,80})"
        ),
    ],
    "customer_name": [
        (
            r"(?:customer\s*name|claimant\s*name)"
            r"\s*[:\-]?\s*"
            r"([A-Za-z][A-Za-z .'\-]{2,80})"
        ),
    ],
    "vehicle_registration_number": [
        (
            r"(?:vehicle\s*registration\s*(?:number|no\.?)|"
            r"vehicle\s*(?:reg\.?|number|no\.?)|"
            r"registration\s*(?:number|no\.?))"
            r"\s*[:\-]?\s*"
            r"([A-Z]{2}[\s\-]?\d{1,2}"
            r"[\s\-]?[A-Z]{1,3}[\s\-]?\d{1,4})"
        ),
    ],
    "vehicle_make": [
        (
            r"(?:vehicle\s*make|make\s+of\s+vehicle|make)"
            r"\s*[:\-]?\s*"
            r"([A-Za-z][A-Za-z0-9 .'\-]{1,40})"
        ),
    ],
    "vehicle_model": [
        (
            r"(?:vehicle\s*model|model\s+of\s+vehicle|model)"
            r"\s*[:\-]?\s*"
            r"([A-Za-z0-9][A-Za-z0-9 .'\-]{1,40})"
        ),
    ],
    "chassis_number": [
        (
            r"(?:chassis|vin)"
            r"\s*(?:number|no\.?|#)?\s*[:\-]?\s*"
            r"([A-HJ-NPR-Z0-9][A-HJ-NPR-Z0-9\-]{5,30})"
        ),
    ],
    "engine_number": [
        (
            r"(?:engine)"
            r"\s*(?:number|no\.?|#)?\s*[:\-]?\s*"
            r"([A-Z0-9][A-Z0-9\-]{4,30})"
        ),
    ],
    "accident_date": [
        (
            r"(?:date\s+of\s+(?:accident|loss)|"
            r"accident\s*date|loss\s*date)"
            r"\s*[:\-]?\s*"
            rf"({DATE_PATTERN})"
        ),
    ],
    "accident_time": [
        (
            r"(?:time\s+of\s+(?:accident|loss)|"
            r"accident\s*time|loss\s*time)"
            r"\s*[:\-]?\s*"
            rf"({TIME_PATTERN})"
        ),
    ],
    "accident_location": [
        (
            r"(?:place\s+of\s+(?:accident|loss)|"
            r"accident\s*(?:place|location)|"
            r"loss\s*location)"
            r"\s*[:\-]?\s*"
            r"([A-Za-z0-9][A-Za-z0-9 ,.'/\-]{2,120})"
        ),
    ],
    "policy_start_date": [
        (
            r"(?:policy\s*(?:start|commencement|from)\s*date|"
            r"period\s+of\s+insurance\s+from|"
            r"policy\s+valid\s+from)"
            r"\s*[:\-]?\s*"
            rf"({DATE_PATTERN})"
        ),
    ],
    "policy_expiry_date": [
        (
            r"(?:policy\s*(?:expiry|expiration|end|to)\s*date|"
            r"period\s+of\s+insurance\s+to|"
            r"policy\s+valid\s+until)"
            r"\s*[:\-]?\s*"
            rf"({DATE_PATTERN})"
        ),
    ],
    "invoice_number": [
        (
            r"(?:invoice|bill)\s*(?:number|no\.?|#)"
            r"\s*[:\-]?\s*"
            r"([A-Z0-9][A-Z0-9/\-]{2,39})"
        ),
    ],
    "invoice_date": [
        (
            r"(?:invoice|bill)\s*(?:date)"
            r"\s*[:\-]?\s*"
            rf"({DATE_PATTERN})"
        ),
    ],
    "claim_amount": [
        (
            r"(?:total\s+claim\s+amount|"
            r"claim\s+amount|"
            r"estimated\s+(?:repair\s+)?cost|"
            r"invoice\s+total|"
            r"net\s+amount|"
            r"amount\s+payable)"
            r"\s*[:\-]?\s*"
            r"((?:INR|Rs\.?)?\s*"
            r"\d[\d,]*(?:\.\d{1,2})?)"
        ),
    ],
    "repair_amount": [
        (
            r"(?:repair\s+amount|"
            r"repair\s+cost|"
            r"total\s+repair\s+charges|"
            r"labour\s+and\s+parts\s+total)"
            r"\s*[:\-]?\s*"
            r"((?:INR|Rs\.?)?\s*"
            r"\d[\d,]*(?:\.\d{1,2})?)"
        ),
    ],
    "garage_name": [
        (
            r"(?:garage|workshop|repairer)"
            r"\s*(?:name)?\s*[:\-]?\s*"
            r"([A-Za-z0-9][A-Za-z0-9 &.'\-]{2,100})"
        ),
    ],
    "driving_licence_number": [
        (
            r"(?:driving\s+licen[cs]e|"
            r"driver'?s?\s+licen[cs]e)"
            r"\s*(?:number|no\.?|#)?\s*[:\-]?\s*"
            r"([A-Z0-9][A-Z0-9/\-]{5,30})"
        ),
    ],
    "driver_name": [
        (
            r"(?:driver\s*name|name\s+of\s+driver)"
            r"\s*[:\-]?\s*"
            r"([A-Za-z][A-Za-z .'\-]{2,80})"
        ),
    ],
    "police_report_number": [
        (
            r"(?:police\s*(?:report|fir)\s*(?:number|no\.?|#)|"
            r"fir\s*(?:number|no\.?|#))"
            r"\s*[:\-]?\s*"
            r"([A-Z0-9][A-Z0-9/\-]{2,39})"
        ),
    ],
}


FIELD_NORMALIZERS: dict[
    str,
    Callable[[str], Any],
] = {
    "policy_number": normalize_uppercase,
    "claim_number": normalize_uppercase,
    "insured_name": normalize_whitespace,
    "customer_name": normalize_whitespace,
    "vehicle_registration_number": normalize_registration_number,
    "vehicle_make": normalize_whitespace,
    "vehicle_model": normalize_whitespace,
    "chassis_number": normalize_uppercase,
    "engine_number": normalize_uppercase,
    "accident_date": normalize_date,
    "accident_time": normalize_time,
    "accident_location": normalize_whitespace,
    "policy_start_date": normalize_date,
    "policy_expiry_date": normalize_date,
    "invoice_number": normalize_uppercase,
    "invoice_date": normalize_date,
    "claim_amount": normalize_amount,
    "repair_amount": normalize_amount,
    "garage_name": normalize_whitespace,
    "driving_licence_number": normalize_uppercase,
    "driver_name": normalize_whitespace,
    "police_report_number": normalize_uppercase,
}


def prepare_searchable_text(text: str) -> str:
    """
    Flatten line breaks so labels and values split across lines
    can still be matched.
    """

    text = text.replace("\x00", " ")

    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]

    searchable_text = " | ".join(lines)

    # Common OCR/direct extraction shape: a label ends one line
    # and its value starts on the next line.
    searchable_text = re.sub(
        r"([:\-])\s*\|\s*",
        r"\1 ",
        searchable_text,
    )

    return searchable_text.strip()


def extract_single_field(
    pages: list[dict[str, Any]],
    field_name: str,
) -> dict[str, Any]:
    """
    Search all pages for one structured field.
    """

    patterns = FIELD_PATTERNS[field_name]
    normalizer = FIELD_NORMALIZERS[field_name]

    for page in pages:
        page_text = prepare_searchable_text(
            str(page.get("text", ""))
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                page_text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            raw_value = match.group(1).strip()

            try:
                normalized_value = normalizer(
                    raw_value
                )
            except (ValueError, TypeError):
                normalized_value = normalize_whitespace(
                    raw_value
                )

            evidence = normalize_whitespace(
                match.group(0)
            )

            if len(evidence) > 250:
                evidence = evidence[:250] + "..."

            return {
                "status": "found",
                "value": normalized_value,
                "raw_value": raw_value,
                "confidence": 0.90,
                "source_page": int(
                    page.get("page_number", 1)
                ),
                "evidence": evidence,
            }

    return {
        "status": "not_found",
        "value": None,
        "raw_value": None,
        "confidence": 0.0,
        "source_page": None,
        "evidence": None,
    }


def load_saved_extraction_result(
    claim_id: str,
    document_id: str,
) -> dict[str, Any]:
    """Load saved document text while keeping OCR imports lazy."""

    from src.documents.extraction import load_extraction_result

    return load_extraction_result(
        claim_id=claim_id,
        document_id=document_id,
    )


def save_field_result(
    claim_id: str,
    document_id: str,
    result: dict[str, Any],
) -> Path:
    """Save structured fields as JSON."""

    output_directory = (
        FIELDS_ROOT
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


def format_result_path(path: Path) -> str:
    """Return project-relative paths when possible."""

    try:
        return str(
            path.relative_to(PROJECT_ROOT)
        )
    except ValueError:
        return str(path)


def extract_structured_fields(
    claim_id: str,
    document_id: str,
) -> dict[str, Any]:
    """
    Extract structured insurance fields from saved OCR/text output.
    """

    cleaned_claim_id = validate_claim_id(
        claim_id
    )

    cleaned_document_id = validate_document_id(
        document_id
    )

    extraction_result = load_saved_extraction_result(
        claim_id=cleaned_claim_id,
        document_id=cleaned_document_id,
    )

    pages = extraction_result.get(
        "pages",
        [],
    )

    if not pages:
        raise ValueError(
            "The extraction result contains no pages."
        )

    extracted_fields = {
        field_name: extract_single_field(
            pages=pages,
            field_name=field_name,
        )
        for field_name in FIELD_PATTERNS
    }

    found_fields = [
        field_name
        for field_name, field_result
        in extracted_fields.items()
        if field_result["status"] == "found"
    ]

    missing_fields = [
        field_name
        for field_name, field_result
        in extracted_fields.items()
        if field_result["status"] == "not_found"
    ]

    result: dict[str, Any] = {
        "claim_id": cleaned_claim_id,
        "document_id": cleaned_document_id,
        "document_type": extraction_result.get(
            "document_type",
            "unknown",
        ),
        "status": "fields_extracted",
        "total_supported_fields": len(
            FIELD_PATTERNS
        ),
        "found_field_count": len(
            found_fields
        ),
        "found_fields": found_fields,
        "missing_fields": missing_fields,
        "fields": extracted_fields,
    }

    output_path = save_field_result(
        claim_id=cleaned_claim_id,
        document_id=cleaned_document_id,
        result=result,
    )

    result["field_result_path"] = format_result_path(
        output_path
    )

    return result


def load_field_result(
    claim_id: str,
    document_id: str,
) -> dict[str, Any]:
    """Load a previously saved structured-field result."""

    cleaned_claim_id = validate_claim_id(
        claim_id
    )

    cleaned_document_id = validate_document_id(
        document_id
    )

    result_path = (
        FIELDS_ROOT
        / cleaned_claim_id
        / f"{cleaned_document_id}.json"
    )

    if not result_path.exists():
        raise FileNotFoundError(
            "No saved structured-field result was found."
        )

    with result_path.open(
        "r",
        encoding="utf-8",
    ) as result_file:
        return json.load(result_file)
