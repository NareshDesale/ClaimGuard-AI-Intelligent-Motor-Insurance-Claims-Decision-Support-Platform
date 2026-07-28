import json

from src.claims.repository import (
    audit_log_to_dict,
    safe_event_data,
)


class FakeAuditLog:
    id = 1
    claim_id = "CLM-AUD-001"
    event_type = "rag_query"
    event_data = '{"question_length": 32}'
    created_at = None

    class __table__:
        columns = []


def test_safe_event_data_redacts_sensitive_keys() -> None:
    serialized = safe_event_data(
        {
            "api_key": "secret-key",
            "nested": {
                "password": "secret-password",
                "safe": "value",
            },
            "items": [
                {
                    "token": "secret-token",
                }
            ],
        }
    )

    assert serialized is not None

    data = json.loads(serialized)

    assert data["api_key"] == "[REDACTED]"
    assert data["nested"]["password"] == "[REDACTED]"
    assert data["nested"]["safe"] == "value"
    assert data["items"][0]["token"] == "[REDACTED]"


def test_audit_log_to_dict_parses_event_data() -> None:
    audit_log = FakeAuditLog()
    audit_log.__table__.columns = [
        type("Column", (), {"name": "id"})(),
        type("Column", (), {"name": "claim_id"})(),
        type("Column", (), {"name": "event_type"})(),
        type("Column", (), {"name": "event_data"})(),
        type("Column", (), {"name": "created_at"})(),
    ]

    result = audit_log_to_dict(audit_log)

    assert result["claim_id"] == "CLM-AUD-001"
    assert result["event_data"] == {
        "question_length": 32,
    }
