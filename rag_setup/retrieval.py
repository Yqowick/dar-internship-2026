from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import Any

from sentence_transformers import CrossEncoder
from weaviate.classes.query import (
    Filter,
    HybridFusion,
    MetadataQuery,
)

from embedding import (
    create_embedding_model,
    embed_query,
)
from vector_store import (
    COLLECTION_NAME,
    connect_to_weaviate,
)


RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

DEFAULT_CANDIDATE_COUNT = 20
DEFAULT_FINAL_COUNT = 5

HYBRID_ALPHA = 0.5
RERANK_BATCH_SIZE = 2
RERANK_MAX_LENGTH = 512


@dataclass
class RetrievalCandidate:
    """A chunk retrieved from Weaviate."""

    content: str
    properties: dict[str, Any]
    retrieval_rank: int
    hybrid_score: float
    rerank_score: float | None = None


def validate_query(query: str) -> str:
    """Clean and validate a user question."""
    cleaned_query = query.strip()

    if not cleaned_query:
        raise ValueError("The query cannot be empty.")

    return cleaned_query


def extract_control_number(
    query: str,
) -> str | None:
    """
    Extract a CIS Control number from a question.

    Examples:
        Control 1  -> 01
        Control 01 -> 01
        CIS Control 18 -> 18
    """
    match = re.search(
        r"\b(?:cis\s+)?control\s+0?(\d{1,2})\b",
        query,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    control_number = int(match.group(1))

    if not 1 <= control_number <= 18:
        return None

    return f"{control_number:02d}"


def build_search_query(
    query: str,
    control_number: str | None,
) -> str:
    """
    Enrich short control-definition questions.

    The original user question is still used for final answer
    generation. This expanded form is only used for retrieval
    and reranking.
    """
    if control_number is None:
        return query

    definition_question = re.search(
        r"\b("
        r"what\s+is|"
        r"what's|"
        r"define|"
        r"describe|"
        r"explain|"
        r"overview|"
        r"purpose"
        r")\b",
        query,
        flags=re.IGNORECASE,
    )

    if definition_question:
        return (
            f"{query} "
            f"Overview, purpose, and definition of "
            f"CIS Control {control_number}."
        )

    return query


def build_keyword_query(
    query: str,
    control_number: str | None,
) -> str:
    """Add common number formats for BM25 keyword retrieval."""
    if control_number is None:
        return query

    numeric_control = int(control_number)

    return (
        f"{query} "
        f"Control {numeric_control} "
        f"Control {control_number} "
        f"CIS Control {control_number}"
    )


def safe_float(value: Any) -> float:
    """Convert a score into a float safely."""
    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def retrieve_candidates(
    client,
    embedding_model,
    query: str,
    candidate_count: int = DEFAULT_CANDIDATE_COUNT,
) -> list[RetrievalCandidate]:
    """
    Retrieve candidate chunks using hybrid search.

    When a valid CIS Control number is present, retrieval is
    restricted to chunks belonging to that exact control.
    """
    if candidate_count < 1:
        raise ValueError(
            "candidate_count must be greater than zero."
        )

    control_number = extract_control_number(query)

    semantic_query = build_search_query(
        query,
        control_number,
    )

    keyword_query = build_keyword_query(
        query,
        control_number,
    )

    query_vector = embed_query(
        embedding_model,
        semantic_query,
    )

    query_filter = None

    if control_number is not None:
        query_filter = Filter.by_property(
            "control_number"
        ).equal(control_number)

    collection = client.collections.get(
        COLLECTION_NAME
    )

    response = collection.query.hybrid(
        query=keyword_query,
        vector=query_vector,
        alpha=HYBRID_ALPHA,
        fusion_type=HybridFusion.RELATIVE_SCORE,
        query_properties=[
            "control_number^8",
            "control_title^5",
            "section_title^4",
            "section_titles^3",
            "content",
        ],
        filters=query_filter,
        limit=candidate_count,
        return_metadata=MetadataQuery(
            score=True,
            explain_score=True,
        ),
    )

    candidates: list[RetrievalCandidate] = []

    for rank, result in enumerate(
        response.objects,
        start=1,
    ):
        properties = dict(result.properties)

        content = str(
            properties.get("content", "")
        ).strip()

        if not content:
            continue

        candidates.append(
            RetrievalCandidate(
                content=content,
                properties=properties,
                retrieval_rank=rank,
                hybrid_score=safe_float(
                    result.metadata.score
                ),
            )
        )

    if not candidates:
        if control_number is not None:
            raise RuntimeError(
                f"No chunks were found for "
                f"CIS Control {control_number}."
            )

        raise RuntimeError(
            "Weaviate returned no retrieval candidates."
        )

    return candidates


def create_reranker() -> CrossEncoder:
    """Load the local BGE reranker."""
    return CrossEncoder(
        model_name_or_path=RERANKER_MODEL_NAME,
        device="cpu",
        max_length=RERANK_MAX_LENGTH,
    )


def rerank_candidates(
    reranker: CrossEncoder,
    query: str,
    candidates: list[RetrievalCandidate],
    final_count: int = DEFAULT_FINAL_COUNT,
) -> list[RetrievalCandidate]:
    """Rerank retrieved chunks and keep the strongest results."""
    if not candidates:
        raise ValueError(
            "No candidates were provided for reranking."
        )

    if final_count < 1:
        raise ValueError(
            "final_count must be greater than zero."
        )

    control_number = extract_control_number(query)

    reranker_query = build_search_query(
        query,
        control_number,
    )

    query_document_pairs = [
        (
            reranker_query,
            candidate.content,
        )
        for candidate in candidates
    ]

    scores = reranker.predict(
        query_document_pairs,
        batch_size=RERANK_BATCH_SIZE,
        show_progress_bar=True,
    )

    if len(scores) != len(candidates):
        raise RuntimeError(
            "The reranker score count does not match "
            "the candidate count."
        )

    for candidate, score in zip(
        candidates,
        scores,
        strict=True,
    ):
        candidate.rerank_score = float(score)

    ranked_candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate.rerank_score
            if candidate.rerank_score is not None
            else float("-inf")
        ),
        reverse=True,
    )

    return ranked_candidates[:final_count]


def format_page_range(
    properties: dict[str, Any],
) -> str:
    """Create a readable page citation."""
    start_page = properties.get("page_number")
    end_page = properties.get("end_page_number")

    if start_page is None:
        return "Unknown"

    if end_page is None or start_page == end_page:
        return str(start_page)

    return f"{start_page}–{end_page}"


def print_results(
    query: str,
    candidates: list[RetrievalCandidate],
) -> None:
    """Print the final reranked chunks."""
    control_number = extract_control_number(query)

    print(f"\nQuery: {query}")

    if control_number is not None:
        print(
            "Metadata filter: "
            f"control_number = {control_number}"
        )
    else:
        print(
            "Metadata filter: none "
            "(general document search)"
        )

    print(
        f"Final reranked results: "
        f"{len(candidates)}"
    )

    for final_rank, candidate in enumerate(
        candidates,
        start=1,
    ):
        properties = candidate.properties

        section_title = properties.get(
            "section_title",
            "Unknown section",
        )

        pages = format_page_range(properties)

        rerank_score = (
            candidate.rerank_score
            if candidate.rerank_score is not None
            else 0.0
        )

        print(
            f"\n--- Reranked Result {final_rank} ---"
        )
        print(
            "Original retrieval rank: "
            f"{candidate.retrieval_rank}"
        )
        print(
            "Hybrid score: "
            f"{candidate.hybrid_score:.6f}"
        )
        print(
            "Reranker score: "
            f"{rerank_score:.6f}"
        )
        print(
            "Control: "
            f"{properties.get('control_number')} "
            f"{properties.get('control_title')}"
        )
        print(f"Pages: {pages}")
        print(f"Section: {section_title}")
        print(
            "Chunk ID: "
            f"{properties.get('chunk_id')}"
        )
        print(
            f"Preview:\n"
            f"{candidate.content[:900]}"
        )


def parse_arguments() -> argparse.Namespace:
    """Read command-line options."""
    parser = argparse.ArgumentParser(
        description=(
            "Retrieve and rerank chunks from the "
            "local CIS Controls vector database."
        )
    )

    parser.add_argument(
        "--query",
        default="What is CIS Control 1?",
        help="Question to search for.",
    )

    parser.add_argument(
        "--candidates",
        type=int,
        default=DEFAULT_CANDIDATE_COUNT,
        help=(
            "Maximum number of chunks retrieved "
            "before reranking."
        ),
    )

    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_FINAL_COUNT,
        help="Number of final reranked chunks.",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    query = validate_query(arguments.query)

    if arguments.top > arguments.candidates:
        raise ValueError(
            "--top cannot be greater than --candidates."
        )

    control_number = extract_control_number(query)

    print("Loading BGE embedding model...")
    embedding_model = create_embedding_model()

    print("Connecting to Weaviate...")
    client = connect_to_weaviate()

    try:
        if control_number is not None:
            print(
                "Detected exact CIS Control reference: "
                f"{control_number}"
            )
        else:
            print(
                "No exact control number detected. "
                "Using general hybrid retrieval."
            )

        print(
            f"Retrieving up to "
            f"{arguments.candidates} candidates..."
        )

        candidates = retrieve_candidates(
            client=client,
            embedding_model=embedding_model,
            query=query,
            candidate_count=arguments.candidates,
        )

        print(
            f"Retrieved candidates: {len(candidates)}"
        )

        print(
            f"Loading reranker: "
            f"{RERANKER_MODEL_NAME}"
        )

        reranker = create_reranker()

        print(
            f"Reranking candidates and keeping "
            f"up to the best {arguments.top}..."
        )

        final_candidates = rerank_candidates(
            reranker=reranker,
            query=query,
            candidates=candidates,
            final_count=arguments.top,
        )

        print_results(
            query=query,
            candidates=final_candidates,
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()