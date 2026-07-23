from __future__ import annotations

from typing import Any

import weaviate
from langchain_core.documents import Document
from weaviate.classes.config import (
    Configure,
    DataType,
    Property,
    VectorDistances,
)
from weaviate.classes.query import MetadataQuery

from embedding import (
    build_chunks,
    create_embedding_model,
    embed_documents,
    embed_query,
    validate_vectors,
)


COLLECTION_NAME = "CISControls"
BATCH_SIZE = 25


def connect_to_weaviate():
    """Connect to the local Weaviate instance."""
    client = weaviate.connect_to_local(
        host="127.0.0.1",
        port=8080,
        grpc_port=50051,
    )

    if not client.is_ready():
        client.close()
        raise RuntimeError(
            "Weaviate is not ready. "
            "Check that Docker Desktop and the Weaviate container are running."
        )

    return client


def create_collection(client) -> None:
    """
    Recreate the CIS collection.

    Recreating it prevents duplicate or outdated chunks after changing
    parsing or chunking logic.
    """
    if client.collections.exists(COLLECTION_NAME):
        client.collections.delete(COLLECTION_NAME)

    client.collections.create(
        name=COLLECTION_NAME,
        vector_config=Configure.Vectors.self_provided(
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=VectorDistances.COSINE,
            )
        ),
        properties=[
            Property(
                name="content",
                data_type=DataType.TEXT,
            ),
            Property(
                name="chunk_id",
                data_type=DataType.TEXT,
            ),
            Property(
                name="source_document",
                data_type=DataType.TEXT,
            ),
            Property(
                name="section_title",
                data_type=DataType.TEXT,
            ),
            Property(
                name="section_titles",
                data_type=DataType.TEXT,
            ),
            Property(
                name="control_number",
                data_type=DataType.TEXT,
            ),
            Property(
                name="control_title",
                data_type=DataType.TEXT,
            ),
            Property(
                name="page_number",
                data_type=DataType.INT,
            ),
            Property(
                name="end_page_number",
                data_type=DataType.INT,
            ),
            Property(
                name="chunk_position",
                data_type=DataType.INT,
            ),
            Property(
                name="token_count",
                data_type=DataType.INT,
            ),
            Property(
                name="category",
                data_type=DataType.TEXT,
            ),
        ],
    )


def chunk_to_properties(
    chunk: Document,
) -> dict[str, Any]:
    """Convert one LangChain chunk into Weaviate properties."""
    metadata = chunk.metadata

    properties: dict[str, Any] = {
        "content": chunk.page_content,
        "chunk_id": str(
            metadata.get("chunk_id", "")
        ),
        "source_document": str(
            metadata.get("source_document", "")
        ),
        "section_title": str(
            metadata.get("section_title", "")
        ),
        "section_titles": str(
            metadata.get("section_titles", "")
        ),
        "control_number": str(
            metadata.get("control_number", "")
        ),
        "control_title": str(
            metadata.get("control_title", "")
        ),
        "category": str(
            metadata.get(
                "category",
                "SectionChunk",
            )
        ),
    }

    integer_properties = {
        "page_number": metadata.get(
            "page_number"
        ),
        "end_page_number": metadata.get(
            "end_page_number"
        ),
        "chunk_position": metadata.get(
            "chunk_position"
        ),
        "token_count": metadata.get(
            "token_count"
        ),
    }

    for property_name, value in integer_properties.items():
        if isinstance(value, int):
            properties[property_name] = value

    return properties


def ingest_chunks(
    client,
    chunks: list[Document],
    vectors: list[list[float]],
) -> int:
    """Store chunks, vectors and metadata in Weaviate."""
    if len(chunks) != len(vectors):
        raise ValueError(
            "Chunk and vector counts must match before ingestion."
        )

    collection = client.collections.get(
        COLLECTION_NAME
    )

    with collection.batch.fixed_size(
        batch_size=BATCH_SIZE
    ) as batch:
        for chunk, vector in zip(
            chunks,
            vectors,
            strict=True,
        ):
            batch.add_object(
                properties=chunk_to_properties(chunk),
                vector=vector,
            )

    failed_objects = collection.batch.failed_objects

    if failed_objects:
        raise RuntimeError(
            f"{len(failed_objects)} objects failed during ingestion. "
            f"First failure: {failed_objects[0]}"
        )

    aggregate_result = collection.aggregate.over_all(
        total_count=True
    )

    stored_count = aggregate_result.total_count or 0

    if stored_count != len(chunks):
        raise RuntimeError(
            f"Expected {len(chunks)} stored chunks, "
            f"but Weaviate contains {stored_count}."
        )

    return stored_count


def test_vector_search(
    client,
    embedding_model,
    query: str,
    limit: int = 3,
) -> None:
    """Perform a basic vector-search smoke test."""
    query_vector = embed_query(
        embedding_model,
        query,
    )

    collection = client.collections.get(
        COLLECTION_NAME
    )

    response = collection.query.near_vector(
        near_vector=query_vector,
        limit=limit,
        return_metadata=MetadataQuery(
            distance=True
        ),
    )

    print(f"\nVector-search test: {query}")

    for position, result in enumerate(
        response.objects,
        start=1,
    ):
        properties = result.properties

        print(f"\n--- Result {position} ---")
        print(
            f"Distance: "
            f"{result.metadata.distance:.6f}"
        )
        print(
            f"Control: "
            f"{properties.get('control_number')} "
            f"{properties.get('control_title')}"
        )
        print(
            "Pages: "
            f"{properties.get('page_number')}–"
            f"{properties.get('end_page_number')}"
        )
        print(
            "Section: "
            f"{properties.get('section_title')}"
        )
        print(
            "Preview: "
            f"{str(properties.get('content', ''))[:500]}"
        )


def main() -> None:
    print("Preparing corrected CIS chunks...")
    chunks = build_chunks()

    print(f"Chunks ready: {len(chunks)}")
    print("Loading the BGE embedding model...")

    embedding_model = create_embedding_model()

    print("Generating document vectors...")
    vectors = embed_documents(
        embedding_model,
        chunks,
    )

    validate_vectors(
        chunks,
        vectors,
    )

    client = connect_to_weaviate()

    try:
        print(
            "Recreating the CISControls collection..."
        )
        create_collection(client)

        print(
            "Ingesting corrected chunks into Weaviate..."
        )
        stored_count = ingest_chunks(
            client,
            chunks,
            vectors,
        )

        print(
            f"Successfully stored {stored_count} "
            "corrected chunks in Weaviate."
        )

        test_vector_search(
            client=client,
            embedding_model=embedding_model,
            query=(
                "What is Control 01 Inventory and "
                "Control of Enterprise Assets?"
            ),
            limit=3,
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()