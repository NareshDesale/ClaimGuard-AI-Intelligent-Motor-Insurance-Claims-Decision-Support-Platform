from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = PROJECT_ROOT / "vector_store" / "policy.index"
CHUNKS_PATH = PROJECT_ROOT / "vector_store" / "policy_chunks.json"

if not INDEX_PATH.exists() or not CHUNKS_PATH.exists():
    pytest.skip(
        "generated policy vector store is required for real RAG tests",
        allow_module_level=True,
    )

from src.rag.service import PolicyRAGService


@pytest.fixture(scope="module")
def rag_service() -> PolicyRAGService:
    try:
        return PolicyRAGService()
    except Exception as error:
        message = str(error).lower()

        if (
            "huggingface.co" in message
            or "socket" in message
            or "connection" in message
            or "network" in message
            or "client has been closed" in message
        ):
            pytest.skip(
                "Embedding model is not available in the local "
                "Hugging Face cache and network access is unavailable."
            )

        raise


def test_real_rag_service_health(
    rag_service: PolicyRAGService,
) -> None:
    service = rag_service

    health = service.health()

    assert health["status"] == "ready"
    assert health["index_loaded"] is True
    assert health["vector_count"] > 0
    assert health["chunk_count"] > 0
    assert health["embedding_dimension"] == 384


def test_policy_retrieval_returns_chunks(
    rag_service: PolicyRAGService,
) -> None:
    results = rag_service.retrieve(
        question=(
            "What third-party liabilities are "
            "covered under this policy?"
        ),
        top_k=4,
    )

    assert len(results) == 4

    for result in results:
        assert result["document"] == (
            "private-car-policy.pdf"
        )
        assert result["page"] > 0
        assert result["text"].strip()
        assert isinstance(
            result["similarity_score"],
            float,
        )


def test_retrieval_preserves_ranking(
    rag_service: PolicyRAGService,
) -> None:
    results = rag_service.retrieve(
        question="What liabilities are covered?",
        top_k=4,
    )

    ranks = [
        result["rank"]
        for result in results
    ]

    assert ranks == [1, 2, 3, 4]
