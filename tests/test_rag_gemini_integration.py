import os

import pytest

from src.rag.service import PolicyRAGService


@pytest.mark.integration
def test_real_gemini_policy_answer() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip(
            "GEMINI_API_KEY is required for this integration test."
        )

    service = PolicyRAGService()
    result = service.answer(
        question="What third-party liabilities are covered?",
        top_k=2,
    )

    assert result["model"]
    assert result["prompt_version"] == "policy_rag_v2"
    assert "sources" in result
