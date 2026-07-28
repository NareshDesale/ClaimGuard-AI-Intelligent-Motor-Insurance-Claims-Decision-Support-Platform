from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "fraud_model.joblib"

if not MODEL_PATH.exists():
    pytest.skip(
        "fraud_model.joblib is required for app RAG API tests",
        allow_module_level=True,
    )

import app as app_module
from src.api.routers import rag as rag_router_module


client = TestClient(app_module.app)


class MockPolicyRAGService:
    """Predictable fake service for API testing."""

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "index_loaded": True,
            "vector_count": 24,
            "embedding_dimension": 384,
            "chunk_count": 24,
            "embedding_model": (
                "sentence-transformers/all-MiniLM-L6-v2"
            ),
            "generation_model": "mock-gemini",
            "api_key_configured": True,
            "source_pdf": "private-car-policy.pdf",
        }

    def answer(
        self,
        question: str,
        top_k: int = 4,
        min_similarity_score: float = 0.25,
    ) -> dict[str, Any]:
        return {
            "question": question,
            "answer": (
                "The policy provides third-party liability "
                "coverage under specified conditions "
                "[Source 1]."
            ),
            "model": "mock-gemini",
            "prompt_version": "policy_rag_v2",
            "answerable": True,
            "refusal_reason": None,
            "retrieved_chunk_count": top_k,
            "latency_ms": 12.5,
            "sources": [
                {
                    "source_number": 1,
                    "document": "private-car-policy.pdf",
                    "page": 2,
                    "similarity_score": 0.75,
                    "excerpt": (
                        "The insurer will indemnify the insured..."
                    ),
                }
            ],
        }

    def retrieve_with_metadata(
        self,
        question: str,
        top_k: int = 4,
        min_similarity_score: float = 0.25,
    ) -> dict[str, Any]:
        return {
            "question": question,
            "answerable": True,
            "refusal_reason": None,
            "top_k": top_k,
            "min_similarity_score": min_similarity_score,
            "retrieved_chunk_count": 1,
            "latency_ms": 3.2,
            "retrieval_method": "semantic",
            "sources": [
                {
                    "rank": 1,
                    "chunk_id": 10,
                    "document": "private-car-policy.pdf",
                    "page": 2,
                    "similarity_score": 0.75,
                    "text": (
                        "The insurer will indemnify the insured..."
                    ),
                }
            ],
        }


def get_mock_rag_service() -> MockPolicyRAGService:
    return MockPolicyRAGService()


def test_rag_health(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_router_module,
        "get_policy_rag_service",
        get_mock_rag_service,
    )

    response = client.get("/rag/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ready"
    assert data["index_loaded"] is True
    assert data["vector_count"] == 24
    assert data["api_key_configured"] is True


def test_rag_ask(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_router_module,
        "get_policy_rag_service",
        get_mock_rag_service,
    )

    response = client.post(
        "/rag/ask",
        json={
            "question": (
                "What third-party liabilities are covered?"
            ),
            "top_k": 4,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "[Source 1]" in data["answer"]
    assert data["retrieved_chunk_count"] == 4
    assert data["prompt_version"] == "policy_rag_v2"
    assert data["answerable"] is True
    assert len(data["sources"]) > 0
    assert data["sources"][0]["page"] > 0


def test_rag_retrieve(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_router_module,
        "get_policy_rag_service",
        get_mock_rag_service,
    )

    response = client.post(
        "/rag/retrieve",
        json={
            "question": (
                "What third-party liabilities are covered?"
            ),
            "top_k": 4,
            "min_similarity_score": 0.25,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["retrieval_method"] == "semantic"
    assert data["answerable"] is True
    assert data["retrieved_chunk_count"] == 1
    assert data["sources"][0]["page"] == 2


def test_rag_rejects_short_question() -> None:
    response = client.post(
        "/rag/ask",
        json={
            "question": "Hi",
            "top_k": 4,
        },
    )

    assert response.status_code == 422


def test_rag_rejects_invalid_top_k() -> None:
    response = client.post(
        "/rag/ask",
        json={
            "question": "What liabilities are covered?",
            "top_k": 20,
        },
    )

    assert response.status_code == 422
