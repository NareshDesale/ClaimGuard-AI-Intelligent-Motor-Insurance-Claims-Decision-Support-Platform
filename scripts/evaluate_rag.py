import argparse
import json
from pathlib import Path
from typing import Any

from src.rag.service import PolicyRAGService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "rag_questions.json"
)


def load_dataset(path: Path) -> list[dict[str, Any]]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as dataset_file:
        return json.load(dataset_file)


def reciprocal_rank(
    sources: list[dict[str, Any]],
    expected_pages: list[int],
) -> float:
    if not expected_pages:
        return 0.0

    for rank, source in enumerate(
        sources,
        start=1,
    ):
        if int(source["page"]) in expected_pages:
            return 1.0 / rank

    return 0.0


def has_expected_keyword(
    sources: list[dict[str, Any]],
    expected_keywords: list[str],
) -> bool:
    if not expected_keywords:
        return False

    combined_text = " ".join(
        str(source.get("text", ""))
        for source in sources
    ).lower()

    return any(
        keyword.lower() in combined_text
        for keyword in expected_keywords
    )


def evaluate(
    dataset: list[dict[str, Any]],
    top_k: int,
    min_similarity_score: float,
) -> dict[str, Any]:
    service = PolicyRAGService()
    recall_hits = 0
    reciprocal_ranks: list[float] = []
    source_page_hits = 0
    refusal_matches = 0

    for item in dataset:
        retrieval = service.retrieve_with_metadata(
            question=item["question"],
            top_k=top_k,
            min_similarity_score=min_similarity_score,
        )
        sources = retrieval["sources"]
        expected_pages = item.get(
            "expected_pages",
            [],
        )
        answerable = bool(
            item.get("answerable", True)
        )
        page_hit = any(
            int(source["page"]) in expected_pages
            for source in sources
        )
        keyword_hit = has_expected_keyword(
            sources,
            item.get("expected_keywords", []),
        )

        if answerable and (page_hit or keyword_hit):
            recall_hits += 1

        if page_hit:
            source_page_hits += 1

        reciprocal_ranks.append(
            reciprocal_rank(
                sources=sources,
                expected_pages=expected_pages,
            )
        )

        if retrieval["answerable"] == answerable:
            refusal_matches += 1

    total = len(dataset)

    return {
        "question_count": total,
        "top_k": top_k,
        "min_similarity_score": min_similarity_score,
        "recall_at_k": (
            round(recall_hits / total, 4)
            if total
            else 0.0
        ),
        "mrr": (
            round(sum(reciprocal_ranks) / total, 4)
            if total
            else 0.0
        ),
        "source_page_hit_rate": (
            round(source_page_hits / total, 4)
            if total
            else 0.0
        ),
        "answer_refusal_accuracy": (
            round(refusal_matches / total, 4)
            if total
            else 0.0
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate ClaimGuard policy RAG retrieval."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--min-similarity-score",
        type=float,
        default=0.25,
    )
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    metrics = evaluate(
        dataset=dataset,
        top_k=args.top_k,
        min_similarity_score=args.min_similarity_score,
    )

    print(
        json.dumps(
            metrics,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
