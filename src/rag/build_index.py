import json
import re
from pathlib import Path
from typing import Any

import faiss
import fitz  # PyMuPDF
import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

# build_index.py location:
# ClaimGuard-AI/src/rag/build_index.py
#
# parents[0] = rag
# parents[1] = src
# parents[2] = ClaimGuard-AI project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

PDF_PATH = (
    PROJECT_ROOT
    / "data"
    / "documents"
    / "private-car-policy.pdf"
)

VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"

INDEX_PATH = VECTOR_STORE_DIR / "policy.index"
CHUNKS_PATH = VECTOR_STORE_DIR / "policy_chunks.json"

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MINIMUM_CHUNK_LENGTH = 50


# ---------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Clean extracted PDF text while preserving paragraph structure.
    """

    # Remove null characters.
    text = text.replace("\x00", " ")

    # Normalize Windows and old Mac line endings.
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Replace multiple spaces and tabs with one space.
    text = re.sub(r"[ \t]+", " ", text)

    # Remove spaces before newline characters.
    text = re.sub(r" +\n", "\n", text)

    # Replace three or more newlines with two newlines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------

def extract_pdf_pages() -> list[dict[str, Any]]:
    """
    Extract text from the policy PDF page by page.

    Page-level extraction is important because it lets the RAG
    response return correct page citations.
    """

    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"Policy PDF was not found:\n{PDF_PATH}\n\n"
            "Make sure the PDF is named "
            "'private-car-policy.pdf' and is stored inside "
            "'data/documents/'."
        )

    pages: list[dict[str, Any]] = []

    print(f"Opening PDF: {PDF_PATH}")

    try:
        with fitz.open(PDF_PATH) as pdf_document:
            total_pages = len(pdf_document)

            print(f"Total PDF pages: {total_pages}")

            for page_index in range(total_pages):
                page = pdf_document.load_page(page_index)

                raw_text = page.get_text("text")
                cleaned_text = clean_text(raw_text)

                page_number = page_index + 1

                if not cleaned_text:
                    print(
                        f"Warning: No selectable text found "
                        f"on page {page_number}."
                    )
                    continue

                pages.append(
                    {
                        "page": page_number,
                        "text": cleaned_text,
                    }
                )

    except fitz.FileDataError as error:
        raise ValueError(
            f"PyMuPDF could not open the PDF: {error}"
        ) from error

    if not pages:
        raise ValueError(
            "No text was extracted from the policy PDF. "
            "The PDF may contain only scanned images and may "
            "require OCR."
        )

    return pages


# ---------------------------------------------------------
# Text chunking
# ---------------------------------------------------------

def create_chunks(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Split each page into smaller overlapping chunks while
    preserving page-number metadata.
    """

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "; ",
            ", ",
            " ",
            "",
        ],
    )

    chunks: list[dict[str, Any]] = []
    chunk_id = 0

    for page_data in pages:
        page_number = int(page_data["page"])
        page_text = str(page_data["text"])

        page_chunks = text_splitter.split_text(page_text)

        for page_chunk_number, page_chunk in enumerate(
            page_chunks,
            start=1,
        ):
            cleaned_chunk = clean_text(page_chunk)

            if len(cleaned_chunk) < MINIMUM_CHUNK_LENGTH:
                continue

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "page_chunk_number": page_chunk_number,
                    "source": PDF_PATH.name,
                    "page": page_number,
                    "text": cleaned_chunk,
                }
            )

            chunk_id += 1

    if not chunks:
        raise ValueError(
            "The PDF text was extracted, but no usable text "
            "chunks were created."
        )

    return chunks


# ---------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------

def generate_embeddings(
    chunks: list[dict[str, Any]],
) -> tuple[np.ndarray, SentenceTransformer]:
    """
    Generate normalized vector embeddings for all policy chunks.
    """

    print(
        "Loading embedding model: "
        f"{EMBEDDING_MODEL_NAME}"
    )

    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        device="cpu",
    )

    chunk_texts = [
        chunk["text"]
        for chunk in chunks
    ]

    print(
        f"Generating embeddings for "
        f"{len(chunk_texts)} chunks..."
    )

    embeddings = embedding_model.encode(
        chunk_texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32,
    )

    if embeddings.ndim != 2:
        raise ValueError(
            "Generated embeddings do not have the expected "
            "two-dimensional shape."
        )

    if embeddings.shape[0] != len(chunks):
        raise ValueError(
            "The number of generated embeddings does not match "
            "the number of chunks."
        )

    return embeddings, embedding_model


# ---------------------------------------------------------
# FAISS index creation
# ---------------------------------------------------------

def create_faiss_index(
    embeddings: np.ndarray,
) -> faiss.Index:
    """
    Create a FAISS inner-product index.

    Because embeddings are normalized, inner product is equivalent
    to cosine similarity.
    """

    embedding_dimension = embeddings.shape[1]

    print(
        f"Embedding dimension: {embedding_dimension}"
    )

    index = faiss.IndexFlatIP(
        embedding_dimension
    )

    index.add(embeddings)

    if index.ntotal != embeddings.shape[0]:
        raise RuntimeError(
            "FAISS did not store all generated embeddings."
        )

    return index


# ---------------------------------------------------------
# Saving vector store and metadata
# ---------------------------------------------------------

def save_vector_store(
    index: faiss.Index,
    chunks: list[dict[str, Any]],
    page_count: int,
) -> None:
    """
    Save the FAISS index and chunk metadata to disk.

    The index is serialized into memory first because
    faiss.write_index() can fail on Windows paths that contain
    Unicode characters.
    """

    VECTOR_STORE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Convert the FAISS index into a NumPy uint8 array.
    serialized_index = faiss.serialize_index(index)

    # Let Python write the bytes because pathlib supports
    # Unicode Windows paths correctly.
    INDEX_PATH.write_bytes(
        serialized_index.tobytes()
    )

    metadata = {
        "source_pdf": PDF_PATH.name,
        "source_pdf_path": str(
            PDF_PATH.relative_to(PROJECT_ROOT)
        ),
        "embedding_model": EMBEDDING_MODEL_NAME,
        "embedding_dimension": index.d,
        "page_count_with_text": page_count,
        "chunk_count": len(chunks),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "chunks": chunks,
    }

    with CHUNKS_PATH.open(
        "w",
        encoding="utf-8",
    ) as metadata_file:
        json.dump(
            metadata,
            metadata_file,
            indent=2,
            ensure_ascii=False,
        )

    if not INDEX_PATH.exists():
        raise RuntimeError(
            "FAISS index file was not created."
        )

    if INDEX_PATH.stat().st_size == 0:
        raise RuntimeError(
            "FAISS index file was created but is empty."
        )

    if not CHUNKS_PATH.exists():
        raise RuntimeError(
            "Chunk metadata file was not created."
        )

    if CHUNKS_PATH.stat().st_size == 0:
        raise RuntimeError(
            "Chunk metadata file was created but is empty."
        )


# ---------------------------------------------------------
# Main execution
# ---------------------------------------------------------

def main() -> None:
    """
    Run the complete PDF indexing pipeline.
    """

    print("=" * 60)
    print("ClaimGuard AI — Policy Index Builder")
    print("=" * 60)

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Policy PDF: {PDF_PATH}")
    print(f"Vector-store directory: {VECTOR_STORE_DIR}")
    print()

    pages = extract_pdf_pages()

    print(
        f"\nPages containing usable text: {len(pages)}"
    )

    chunks = create_chunks(pages)

    print(f"Text chunks created: {len(chunks)}")

    embeddings, _ = generate_embeddings(chunks)

    print(
        f"Embeddings shape: {embeddings.shape}"
    )

    index = create_faiss_index(embeddings)

    print(
        f"Vectors stored in FAISS: {index.ntotal}"
    )

    save_vector_store(
        index=index,
        chunks=chunks,
        page_count=len(pages),
    )

    print()
    print("=" * 60)
    print("Policy index created successfully")
    print("=" * 60)
    print(f"FAISS index: {INDEX_PATH}")
    print(f"Chunk metadata: {CHUNKS_PATH}")
    print(f"Total pages indexed: {len(pages)}")
    print(f"Total chunks indexed: {len(chunks)}")


if __name__ == "__main__":
    main()