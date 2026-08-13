from __future__ import annotations

import math

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from chunking import (
    create_chunks,
    group_elements_into_sections,
)
from clean_pdf import PDF_PATH, load_or_parse_pdf


EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

QUERY_INSTRUCTION = (
    "Represent this sentence for searching relevant passages: "
)

EMBEDDING_BATCH_SIZE = 16


def create_embedding_model() -> HuggingFaceEmbeddings:
    """
    Load the local BGE embedding model.

    Embeddings are normalized so cosine similarity can be used
    consistently during retrieval.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={
            "device": "cpu",
        },
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": EMBEDDING_BATCH_SIZE,
        },
        show_progress=True,
    )


def embed_documents(
    embedding_model: HuggingFaceEmbeddings,
    chunks: list[Document],
) -> list[list[float]]:
    """Convert all chunk texts into embedding vectors."""
    if not chunks:
        raise ValueError("No chunks were provided for embedding.")

    texts = [
        chunk.page_content
        for chunk in chunks
    ]

    vectors = embedding_model.embed_documents(texts)

    if len(vectors) != len(chunks):
        raise RuntimeError(
            "The number of generated vectors does not match "
            "the number of chunks."
        )

    return vectors


def embed_query(
    embedding_model: HuggingFaceEmbeddings,
    query: str,
) -> list[float]:
    """
    Convert a user question into an embedding vector.

    The BGE query instruction helps the model understand that the
    text is a search query rather than a stored document.
    """
    cleaned_query = query.strip()

    if not cleaned_query:
        raise ValueError("The query cannot be empty.")

    instructed_query = (
        f"{QUERY_INSTRUCTION}{cleaned_query}"
    )

    return embedding_model.embed_query(
        instructed_query
    )


def vector_norm(vector: list[float]) -> float:
    """Calculate the Euclidean norm of an embedding vector."""
    return math.sqrt(
        sum(value * value for value in vector)
    )


def validate_vectors(
    chunks: list[Document],
    vectors: list[list[float]],
) -> None:
    """Validate generated vectors before storing them."""
    if not vectors:
        raise RuntimeError("No embedding vectors were generated.")

    vector_dimension = len(vectors[0])

    if vector_dimension == 0:
        raise RuntimeError(
            "The generated vectors have no dimensions."
        )

    for index, vector in enumerate(vectors):
        if len(vector) != vector_dimension:
            raise RuntimeError(
                f"Vector {index} has an inconsistent dimension."
            )

        if not all(math.isfinite(value) for value in vector):
            raise RuntimeError(
                f"Vector {index} contains an invalid numeric value."
            )

    if len(chunks) != len(vectors):
        raise RuntimeError(
            "Chunk and vector counts do not match."
        )


def build_chunks() -> list[Document]:
    """Load cached parsing results and create final chunks."""
    parsed_elements = load_or_parse_pdf(PDF_PATH)

    sections = group_elements_into_sections(
        parsed_elements
    )

    return create_chunks(sections)


def main() -> None:
    chunks = build_chunks()

    print(f"Chunks ready for embedding: {len(chunks)}")
    print(
        f"Loading embedding model: "
        f"{EMBEDDING_MODEL_NAME}"
    )

    embedding_model = create_embedding_model()

    vectors = embed_documents(
        embedding_model,
        chunks,
    )

    validate_vectors(
        chunks,
        vectors,
    )

    test_query = "What is CIS Control 1?"

    query_vector = embed_query(
        embedding_model,
        test_query,
    )

    print("\nEmbedding validation:")
    print(f"Document vectors: {len(vectors)}")
    print(f"Vector dimension: {len(vectors[0])}")
    print(
        "First document vector norm: "
        f"{vector_norm(vectors[0]):.6f}"
    )
    print(
        "Query vector dimension: "
        f"{len(query_vector)}"
    )
    print(
        "Query vector norm: "
        f"{vector_norm(query_vector):.6f}"
    )
    print(
        "First vector preview: "
        f"{vectors[0][:5]}"
    )


if __name__ == "__main__":
    main()