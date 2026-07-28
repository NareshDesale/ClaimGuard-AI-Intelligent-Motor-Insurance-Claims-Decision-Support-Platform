import json
import logging
import time
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from google import genai
from google.genai import types

from src.config import get_settings


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = get_settings()

INDEX_PATH = SETTINGS.vector_index_path

CHUNKS_PATH = SETTINGS.vector_metadata_path

DEFAULT_MODEL_NAME = "gemini-3.6-flash"
DEFAULT_TOP_K = 4
DEFAULT_MIN_SIMILARITY_SCORE = 0.25
PROMPT_VERSION = "policy_rag_v2"
INSUFFICIENT_EVIDENCE_ANSWER = (
    "The retrieved policy text does not contain enough "
    "information to answer this question."
)

logger = logging.getLogger(__name__)


class PolicyRAGService:
    """
    Retrieve relevant motor-policy clauses from FAISS and use
    Gemini to generate a grounded answer with page citations.
    """

    def __init__(self) -> None:
        settings = get_settings()

        self._validate_required_files()
        self.metadata = self._load_metadata()
        self.chunks = self.metadata["chunks"]

        self.embedding_model_name = self.metadata[
            "embedding_model"
        ]

        self.index = self._load_faiss_index()

        self._validate_index()

        logger.info(
            "Loading embedding model: %s",
            self.embedding_model_name,
        )

        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "sentence-transformers is not installed. Install "
                "project RAG dependencies before using policy RAG."
            ) from error

        self.embedding_model = SentenceTransformer(
            self.embedding_model_name,
            device="cpu",
        )

        self.api_key = settings.gemini_api_key

        self.model_name = settings.gemini_model or DEFAULT_MODEL_NAME

        self.client = (
            genai.Client(api_key=self.api_key)
            if self.api_key
            else None
        )

    # -----------------------------------------------------
    # Initialisation helpers
    # -----------------------------------------------------

    @staticmethod
    def _validate_required_files() -> None:
        """Check that the generated vector-store files exist."""

        if not INDEX_PATH.exists():
            raise FileNotFoundError(
                f"FAISS index not found:\n{INDEX_PATH}\n\n"
                "Run this command first:\n"
                "python -m src.rag.build_index"
            )

        if not CHUNKS_PATH.exists():
            raise FileNotFoundError(
                f"Chunk metadata not found:\n{CHUNKS_PATH}\n\n"
                "Run this command first:\n"
                "python -m src.rag.build_index"
            )

        if INDEX_PATH.stat().st_size == 0:
            raise ValueError(
                "The FAISS index file exists but is empty."
            )

        if CHUNKS_PATH.stat().st_size == 0:
            raise ValueError(
                "The chunk metadata file exists but is empty."
            )

    @staticmethod
    def _load_metadata() -> dict[str, Any]:
        """Read chunk metadata stored during indexing."""

        with CHUNKS_PATH.open(
            "r",
            encoding="utf-8",
        ) as metadata_file:
            metadata = json.load(metadata_file)

        required_keys = {
            "embedding_model",
            "chunks",
            "chunk_count",
        }

        missing_keys = required_keys.difference(
            metadata.keys()
        )

        if missing_keys:
            raise ValueError(
                "Metadata is missing required fields: "
                + ", ".join(sorted(missing_keys))
            )

        if not isinstance(metadata["chunks"], list):
            raise ValueError(
                "The 'chunks' metadata value must be a list."
            )

        if not metadata["chunks"]:
            raise ValueError(
                "No policy chunks were found in metadata."
            )

        return metadata

    @staticmethod
    def _load_faiss_index() -> faiss.Index:
        """
        Load FAISS through Python bytes.

        This avoids Windows path errors when the project path
        contains Unicode characters.
        """

        index_bytes = INDEX_PATH.read_bytes()

        index_array = np.frombuffer(
            index_bytes,
            dtype=np.uint8,
        ).copy()

        try:
            return faiss.deserialize_index(
                index_array
            )

        except Exception as error:
            raise RuntimeError(
                f"Unable to deserialize FAISS index: {error}"
            ) from error

    def _validate_index(self) -> None:
        """Ensure index vectors and metadata chunks match."""

        if self.index.ntotal == 0:
            raise ValueError(
                "The loaded FAISS index contains no vectors."
            )

        if self.index.ntotal != len(self.chunks):
            raise ValueError(
                "FAISS vector count does not match the "
                "number of stored policy chunks. "
                f"Vectors: {self.index.ntotal}, "
                f"chunks: {len(self.chunks)}"
            )

        metadata_dimension = self.metadata.get(
            "embedding_dimension"
        )

        if (
            metadata_dimension is not None
            and self.index.d != metadata_dimension
        ):
            raise ValueError(
                "FAISS dimension does not match metadata. "
                f"Index dimension: {self.index.d}, "
                f"metadata dimension: {metadata_dimension}"
            )

    # -----------------------------------------------------
    # Health information
    # -----------------------------------------------------

    @property
    def api_key_configured(self) -> bool:
        return self.client is not None

    def health(self) -> dict[str, Any]:
        """Return service and vector-index information."""

        return {
            "status": "ready",
            "index_loaded": True,
            "vector_count": int(self.index.ntotal),
            "embedding_dimension": int(self.index.d),
            "chunk_count": len(self.chunks),
            "embedding_model": self.embedding_model_name,
            "generation_model": self.model_name,
            "api_key_configured": (
                self.api_key_configured
            ),
            "source_pdf": self.metadata.get(
                "source_pdf"
            ),
        }

    # -----------------------------------------------------
    # Retrieval
    # -----------------------------------------------------

    def retrieve(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity_score: float = DEFAULT_MIN_SIMILARITY_SCORE,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the policy chunks most similar to the question.
        """
        return self.retrieve_with_metadata(
            question=question,
            top_k=top_k,
            min_similarity_score=min_similarity_score,
        )["sources"]


    def retrieve_with_metadata(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity_score: float = DEFAULT_MIN_SIMILARITY_SCORE,
    ) -> dict[str, Any]:
        """
        Retrieve policy chunks and include refusal/latency metadata.
        """

        start_time = time.perf_counter()

        cleaned_question = question.strip()

        if len(cleaned_question) < 3:
            raise ValueError(
                "Question must contain at least "
                "three characters."
            )

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        if min_similarity_score < -1 or min_similarity_score > 1:
            raise ValueError(
                "min_similarity_score must be between -1 and 1."
            )

        top_k = min(
            top_k,
            len(self.chunks),
        )

        query_embedding = self.embedding_model.encode(
            [cleaned_question],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype=np.float32,
        )

        search_k = min(
            len(self.chunks),
            max(top_k * 3, top_k),
        )

        scores, indices = self.index.search(
            query_embedding,
            search_k,
        )

        results: list[dict[str, Any]] = []
        seen_chunk_ids: set[int] = set()

        for similarity_score, chunk_index in zip(
            scores[0],
            indices[0],
        ):
            if chunk_index < 0:
                continue

            chunk = self.chunks[
                int(chunk_index)
            ]
            chunk_id = int(chunk["chunk_id"])

            if chunk_id in seen_chunk_ids:
                continue

            seen_chunk_ids.add(chunk_id)

            if float(similarity_score) < min_similarity_score:
                continue

            results.append(
                {
                    "rank": len(results) + 1,
                    "chunk_id": chunk_id,
                    "document": chunk["source"],
                    "page": int(chunk["page"]),
                    "similarity_score": round(
                        float(similarity_score),
                        4,
                    ),
                    "text": chunk["text"],
                }
            )

            if len(results) >= top_k:
                break

        latency_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )
        answerable = bool(results)

        return {
            "question": question,
            "answerable": answerable,
            "refusal_reason": (
                None
                if answerable
                else (
                    "No retrieved policy chunks met the minimum "
                    "similarity threshold."
                )
            ),
            "top_k": top_k,
            "min_similarity_score": min_similarity_score,
            "retrieved_chunk_count": len(results),
            "latency_ms": latency_ms,
            "retrieval_method": "semantic",
            "sources": results,
        }

    # -----------------------------------------------------
    # Prompt construction
    # -----------------------------------------------------

    @staticmethod
    def build_context(
        retrieved_chunks: list[dict[str, Any]],
    ) -> str:
        """
        Convert retrieved chunks into numbered policy sources.
        """

        context_sections: list[str] = []

        for source_number, chunk in enumerate(
            retrieved_chunks,
            start=1,
        ):
            section = (
                f"[Source {source_number}]\n"
                f"Document: {chunk['document']}\n"
                f"Page: {chunk['page']}\n"
                f"Similarity score: "
                f"{chunk['similarity_score']}\n"
                f"Policy text:\n"
                f"{chunk['text']}"
            )

            context_sections.append(section)

        return "\n\n--------------------\n\n".join(
            context_sections
        )

    @staticmethod
    def create_source_response(
        retrieved_chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Create shortened source details for the API response."""

        sources: list[dict[str, Any]] = []

        for source_number, chunk in enumerate(
            retrieved_chunks,
            start=1,
        ):
            excerpt = chunk["text"].strip()

            if len(excerpt) > 500:
                excerpt = (
                    excerpt[:500].rstrip()
                    + "..."
                )

            sources.append(
                {
                    "source_number": source_number,
                    "document": chunk["document"],
                    "page": chunk["page"],
                    "similarity_score": (
                        chunk["similarity_score"]
                    ),
                    "excerpt": excerpt,
                }
            )

        return sources

    # -----------------------------------------------------
    # Answer generation
    # -----------------------------------------------------

    def answer(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity_score: float = DEFAULT_MIN_SIMILARITY_SCORE,
    ) -> dict[str, Any]:
        """
        Retrieve policy text and generate a grounded Gemini answer.
        """
        start_time = time.perf_counter()

        retrieval_result = self.retrieve_with_metadata(
            question=question,
            top_k=top_k,
            min_similarity_score=min_similarity_score,
        )
        retrieved_chunks = retrieval_result["sources"]

        if not retrieved_chunks:
            return {
                "question": question,
                "answer": INSUFFICIENT_EVIDENCE_ANSWER,
                "model": self.model_name,
                "prompt_version": PROMPT_VERSION,
                "answerable": False,
                "refusal_reason": retrieval_result[
                    "refusal_reason"
                ],
                "retrieved_chunk_count": 0,
                "sources": [],
                "latency_ms": round(
                    (time.perf_counter() - start_time) * 1000,
                    2,
                ),
            }

        if self.client is None:
            raise RuntimeError(
                "GEMINI_API_KEY is missing from the .env file."
            )

        context = self.build_context(
            retrieved_chunks
        )

        prompt = f"""
You are answering a question about a motor-insurance policy.

USER QUESTION:
{question}

RETRIEVED POLICY SOURCES:
{context}

PROMPT VERSION:
{PROMPT_VERSION}

STRICT INSTRUCTIONS:

1. Answer only from the retrieved policy sources.
2. Do not use outside insurance knowledge.
3. Do not invent coverage, exclusions, limits, conditions,
   compensation amounts or legal conclusions.
4. Cite important statements using [Source 1], [Source 2],
   [Source 3], etc.
5. The source numbers must match the retrieved sources.
6. If the retrieved text is insufficient, clearly say:
   "{INSUFFICIENT_EVIDENCE_ANSWER}"
7. Do not approve or reject an insurance claim.
8. Do not describe a risk prediction as proof of fraud.
9. Explain the answer in clear and simple English.
10. Keep the answer focused on the user's question.
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=700,
                ),
            )

        except Exception as error:
            raise RuntimeError(
                f"Gemini answer generation failed: {error}"
            ) from error

        answer_text = response.text

        if not answer_text:
            answer_text = (
                "Gemini returned an empty response."
            )

        return {
            "question": question,
            "answer": answer_text.strip(),
            "model": self.model_name,
            "prompt_version": PROMPT_VERSION,
            "answerable": True,
            "refusal_reason": None,
            "retrieved_chunk_count": len(
                retrieved_chunks
            ),
            "sources": self.create_source_response(
                retrieved_chunks
            ),
            "latency_ms": round(
                (time.perf_counter() - start_time) * 1000,
                2,
            ),
        }
