import json

from src.rag.service import PolicyRAGService


def main() -> None:
    print("=" * 60)
    print("ClaimGuard AI - Policy RAG Service Test")
    print("=" * 60)

    service = PolicyRAGService()

    print("\nService health:")
    print(
        json.dumps(
            service.health(),
            indent=2,
        )
    )

    question = (
        "What third-party liabilities are "
        "covered under this policy?"
    )

    print("\nQuestion:")
    print(question)

    print("\nRetrieving policy chunks...")

    retrieved_chunks = service.retrieve(
        question=question,
        top_k=4,
    )

    for chunk in retrieved_chunks:
        print(
            f"\nRank: {chunk['rank']}"
            f"\nDocument: {chunk['document']}"
            f"\nPage: {chunk['page']}"
            f"\nScore: {chunk['similarity_score']}"
            f"\nText: {chunk['text'][:300]}..."
        )

    print("\nGenerating Gemini answer...")

    result = service.answer(
        question=question,
        top_k=4,
    )

    print("\nFinal result:")
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()