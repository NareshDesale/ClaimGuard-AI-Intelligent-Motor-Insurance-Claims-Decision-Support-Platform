from __future__ import annotations

import pytest

from scripts.smoke_test import (
    SmokeTestError,
    build_url,
    require_status,
)


def test_build_url_handles_slashes() -> None:
    assert (
        build_url("http://127.0.0.1:8000/", "/health")
        == "http://127.0.0.1:8000/health"
    )


def test_require_status_passes_expected_status() -> None:
    result = require_status(
        "health",
        200,
        {200},
        {"api_status": "healthy"},
    )

    assert result.name == "health"
    assert result.status == "passed"
    assert result.details["http_status"] == 200


def test_require_status_raises_for_unexpected_status() -> None:
    with pytest.raises(SmokeTestError) as error:
        require_status(
            "health",
            500,
            {200},
            {"detail": "broken"},
        )

    assert "health failed with HTTP 500" in str(error.value)
