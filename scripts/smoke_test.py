from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class SmokeResult:
    name: str
    status: str
    details: JsonObject


class SmokeTestError(RuntimeError):
    """Raised when a required smoke-test check fails."""


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: JsonObject | None = None,
    timeout_seconds: float = 15.0,
) -> tuple[int, JsonObject]:
    body = None
    headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        build_url(base_url, path),
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            data = response.read().decode("utf-8")
            return response.status, json.loads(data or "{}")
    except HTTPError as error:
        data = error.read().decode("utf-8")
        try:
            payload_data: JsonObject = json.loads(data or "{}")
        except json.JSONDecodeError:
            payload_data = {"detail": data}
        return error.code, payload_data
    except URLError as error:
        raise SmokeTestError(
            "Could not connect to the FastAPI backend. Start it with "
            "'.\\scripts\\run_backend.ps1' and try again."
        ) from error


def require_status(
    name: str,
    actual_status: int,
    expected_statuses: set[int],
    details: JsonObject,
) -> SmokeResult:
    if actual_status not in expected_statuses:
        raise SmokeTestError(
            f"{name} failed with HTTP {actual_status}: "
            f"{json.dumps(details, ensure_ascii=False)}"
        )

    return SmokeResult(
        name=name,
        status="passed",
        details={
            "http_status": actual_status,
            **details,
        },
    )


def run_smoke_test(
    *,
    base_url: str,
    claim_id: str,
    include_rag: bool,
) -> list[SmokeResult]:
    results: list[SmokeResult] = []

    status, payload = request_json(base_url, "/health")
    results.append(
        require_status(
            "health",
            status,
            {200},
            {
                "api_status": payload.get("status"),
                "fraud_model_loaded": payload.get("fraud_model_loaded"),
                "expected_feature_count": payload.get(
                    "expected_feature_count"
                ),
            },
        )
    )

    status, payload = request_json(base_url, "/model/features")
    results.append(
        require_status(
            "model_features",
            status,
            {200},
            {
                "feature_count": payload.get("feature_count"),
                "source": payload.get("source"),
            },
        )
    )

    claim_payload: JsonObject = {
        "claim_id": claim_id,
        "policy_number": "POL-SMOKE-001",
        "customer_name": "Demo Smoke Reviewer",
        "vehicle_number": "MH12SM1234",
        "accident_date": "2026-07-20",
        "reported_date": "2026-07-21",
        "claimed_amount": 42500,
        "status": "open",
    }

    status, payload = request_json(
        base_url,
        "/claims",
        method="POST",
        payload=claim_payload,
    )
    results.append(
        require_status(
            "create_claim",
            status,
            {200, 409},
            {
                "claim_id": claim_id,
                "created_or_existing": status == 200,
                "detail": payload.get("detail"),
            },
        )
    )

    status, payload = request_json(base_url, f"/claims/{claim_id}")
    results.append(
        require_status(
            "get_claim",
            status,
            {200},
            {
                "claim_id": payload.get("claim_id"),
                "status": payload.get("status"),
            },
        )
    )

    status, payload = request_json(
        base_url,
        f"/claims/{claim_id}/documents",
    )
    results.append(
        require_status(
            "list_claim_documents",
            status,
            {200},
            {
                "document_count": payload.get("count"),
            },
        )
    )

    status, payload = request_json(
        base_url,
        f"/claims/{claim_id}/completeness",
    )
    results.append(
        require_status(
            "completeness",
            status,
            {200},
            {
                "completion_status": payload.get("status"),
                "completion_percentage": payload.get(
                    "completion_percentage"
                ),
            },
        )
    )

    status, payload = request_json(
        base_url,
        f"/claims/{claim_id}/validate",
        method="POST",
    )
    results.append(
        require_status(
            "cross_document_validation",
            status,
            {200},
            {
                "rule_count": len(payload.get("results", [])),
            },
        )
    )

    if include_rag:
        status, payload = request_json(base_url, "/rag/health")
        results.append(
            require_status(
                "rag_health",
                status,
                {200, 503},
                {
                    "rag_ready": status == 200,
                    "detail": payload.get("detail"),
                },
            )
        )

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a lightweight ClaimGuard AI backend smoke test.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="FastAPI backend base URL.",
    )
    parser.add_argument(
        "--claim-id",
        default=(
            "SMOKE-"
            + datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        ),
        help="Claim ID to create or reuse during the smoke test.",
    )
    parser.add_argument(
        "--skip-rag",
        action="store_true",
        help="Skip the optional RAG readiness check.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        results = run_smoke_test(
            base_url=args.base_url,
            claim_id=args.claim_id,
            include_rag=not args.skip_rag,
        )
    except SmokeTestError as error:
        print(f"Smoke test failed: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "passed",
                "base_url": args.base_url,
                "claim_id": args.claim_id,
                "checks": [
                    result.__dict__
                    for result in results
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
