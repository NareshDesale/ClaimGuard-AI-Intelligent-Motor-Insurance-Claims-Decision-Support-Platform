from typing import Any

import numpy as np

from src.rag import service as rag_service


class FakeEmbeddingModel:
    def encode(
        self,
        texts: list[str],
        convert_to_numpy: bool,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> np.ndarray:
        return np.asarray(
            [[1.0, 0.0]],
            dtype=np.float32,
        )


class FakeIndex:
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        return (
            np.asarray([[0.9, 0.9, 0.1]], dtype=np.float32),
            np.asarray([[0, 0, 1]], dtype=np.int64),
        )


def fake_service() -> rag_service.PolicyRAGService:
    service = object.__new__(
        rag_service.PolicyRAGService
    )
    service.chunks = [
        {
            "chunk_id": 1,
            "source": "private-car-policy.pdf",
            "page": 2,
            "text": "Covered third-party liabilities.",
        },
        {
            "chunk_id": 2,
            "source": "private-car-policy.pdf",
            "page": 9,
            "text": "Unrelated policy text.",
        },
    ]
    service.index = FakeIndex()
    service.embedding_model = FakeEmbeddingModel()
    service.model_name = "mock-gemini"
    service.client = None

    return service


def test_retrieve_with_metadata_filters_duplicates_and_threshold() -> None:
    service = fake_service()

    result = service.retrieve_with_metadata(
        question="What liabilities are covered?",
        top_k=2,
        min_similarity_score=0.25,
    )

    assert result["answerable"] is True
    assert result["retrieved_chunk_count"] == 1
    assert result["sources"][0]["chunk_id"] == 1
    assert result["sources"][0]["rank"] == 1


def test_retrieve_with_metadata_refuses_below_threshold() -> None:
    service = fake_service()

    result = service.retrieve_with_metadata(
        question="What liabilities are covered?",
        top_k=2,
        min_similarity_score=0.95,
    )

    assert result["answerable"] is False
    assert result["retrieved_chunk_count"] == 0
    assert result["refusal_reason"]


def test_answer_refuses_when_retrieval_is_insufficient() -> None:
    service = fake_service()
    service.client = object()

    result = service.answer(
        question="What liabilities are covered?",
        top_k=2,
        min_similarity_score=0.95,
    )

    assert result["answerable"] is False
    assert result["answer"] == (
        rag_service.INSUFFICIENT_EVIDENCE_ANSWER
    )
    assert result["sources"] == []
