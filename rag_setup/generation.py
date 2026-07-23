from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from embedding import create_embedding_model
from retrieval import (
    DEFAULT_CANDIDATE_COUNT,
    DEFAULT_FINAL_COUNT,
    RetrievalCandidate,
    create_reranker,
    extract_control_number,
    rerank_candidates,
    retrieve_candidates,
    validate_query,
)
from vector_store import connect_to_weaviate


OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_MODEL_NAME = "qwen2.5:3b"

REFUSAL_MESSAGE = (
    "The retrieved documents do not contain enough "
    "information to answer this question."
)

REQUEST_TIMEOUT_SECONDS = 300


@dataclass
class Source:
    """One validated source supporting the final answer."""

    source_id: int
    chunk_id: str
    source_document: str
    section_title: str
    page_number: int | None
    end_page_number: int | None


@dataclass
class GeneratedAnswer:
    """The grounded answer and its validated sources."""

    answer: str
    sources: list[Source]


def is_definition_question(question: str) -> bool:
    """Detect a question asking for a definition or overview."""
    return bool(
        re.search(
            r"\b("
            r"what\s+is|"
            r"what's|"
            r"define|"
            r"describe|"
            r"explain|"
            r"overview|"
            r"purpose"
            r")\b",
            question,
            flags=re.IGNORECASE,
        )
    )


def is_main_control_overview(
    candidate: RetrievalCandidate,
) -> bool:
    """Check whether a candidate is the main control overview."""
    properties = candidate.properties

    control_number = str(
        properties.get("control_number", "")
    ).strip()

    control_title = str(
        properties.get("control_title", "")
    ).strip()

    section_title = str(
        properties.get("section_title", "")
    ).strip()

    if not control_number or not control_title:
        return False

    expected_title = (
        f"Control {control_number}: {control_title}"
    )

    return (
        section_title.casefold()
        == expected_title.casefold()
    )


def order_context_candidates(
    question: str,
    candidates: list[RetrievalCandidate],
) -> list[RetrievalCandidate]:
    """
    Put the main control overview first for definition questions.

    Other candidates keep their reranked order.
    """
    if (
        extract_control_number(question) is None
        or not is_definition_question(question)
    ):
        return candidates

    overview_candidates = [
        candidate
        for candidate in candidates
        if is_main_control_overview(candidate)
    ]

    other_candidates = [
        candidate
        for candidate in candidates
        if not is_main_control_overview(candidate)
    ]

    return [
        *overview_candidates,
        *other_candidates,
    ]


def has_verified_control_evidence(
    question: str,
    candidates: list[RetrievalCandidate],
) -> bool:
    """
    Verify exact CIS Control evidence using structured metadata.

    This avoids asking the LLM to decide something that Python can
    determine reliably.
    """
    requested_control = extract_control_number(
        question
    )

    if requested_control is None:
        return False

    matching_candidates = [
        candidate
        for candidate in candidates
        if str(
            candidate.properties.get(
                "control_number",
                "",
            )
        ).strip()
        == requested_control
    ]

    if not matching_candidates:
        return False

    if is_definition_question(question):
        return any(
            is_main_control_overview(candidate)
            for candidate in matching_candidates
        )

    return True


def format_page_range(
    properties: dict[str, Any],
) -> str:
    """Return a readable page range."""
    start_page = properties.get("page_number")
    end_page = properties.get("end_page_number")

    if start_page is None:
        return "Unknown"

    if (
        end_page is None
        or start_page == end_page
    ):
        return str(start_page)

    return f"{start_page}-{end_page}"


def build_context(
    candidates: list[RetrievalCandidate],
) -> str:
    """Format retrieved chunks for Qwen."""
    context_blocks: list[str] = []

    for source_id, candidate in enumerate(
        candidates,
        start=1,
    ):
        properties = candidate.properties

        context_blocks.append(
            "\n".join(
                [
                    f"[Source {source_id}]",
                    (
                        "Document: "
                        f"{properties.get('source_document')}"
                    ),
                    (
                        "Control number: "
                        f"{properties.get('control_number')}"
                    ),
                    (
                        "Control title: "
                        f"{properties.get('control_title')}"
                    ),
                    (
                        "Section: "
                        f"{properties.get('section_title')}"
                    ),
                    (
                        "Pages: "
                        f"{format_page_range(properties)}"
                    ),
                    (
                        "Chunk ID: "
                        f"{properties.get('chunk_id')}"
                    ),
                    "Content:",
                    candidate.content,
                ]
            )
        )

    return "\n\n".join(context_blocks)


def build_sources(
    candidates: list[RetrievalCandidate],
) -> list[Source]:
    """Create source records for the retrieved candidates."""
    sources: list[Source] = []

    for source_id, candidate in enumerate(
        candidates,
        start=1,
    ):
        properties = candidate.properties

        sources.append(
            Source(
                source_id=source_id,
                chunk_id=str(
                    properties.get("chunk_id", "")
                ),
                source_document=str(
                    properties.get(
                        "source_document",
                        "",
                    )
                ),
                section_title=str(
                    properties.get(
                        "section_title",
                        "",
                    )
                ),
                page_number=properties.get(
                    "page_number"
                ),
                end_page_number=properties.get(
                    "end_page_number"
                ),
            )
        )

    return sources


def check_ollama() -> None:
    """Confirm that Ollama and Qwen are available."""
    request = urllib.request.Request(
        OLLAMA_TAGS_URL,
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )

    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as error:
        raise RuntimeError(
            "Ollama is not available at "
            "http://127.0.0.1:11434. "
            "Start Ollama and try again."
        ) from error

    available_models: set[str] = set()

    for model in payload.get("models", []):
        available_models.add(
            str(model.get("name", ""))
        )
        available_models.add(
            str(model.get("model", ""))
        )

    if OLLAMA_MODEL_NAME not in available_models:
        raise RuntimeError(
            f"Required Ollama model "
            f"'{OLLAMA_MODEL_NAME}' was not found."
        )


def verified_response_schema() -> dict[str, Any]:
    """
    Schema used when Python has already verified direct evidence.

    Qwen only writes the answer and selects supporting sources.
    """
    return {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
            },
            "source_ids": {
                "type": "array",
                "items": {
                    "type": "integer",
                },
            },
        },
        "required": [
            "answer",
            "source_ids",
        ],
    }


def unverified_response_schema() -> dict[str, Any]:
    """Schema used for general questions without exact metadata."""
    return {
        "type": "object",
        "properties": {
            "answerable": {
                "type": "boolean",
            },
            "answer": {
                "type": "string",
            },
            "source_ids": {
                "type": "array",
                "items": {
                    "type": "integer",
                },
            },
        },
        "required": [
            "answerable",
            "answer",
            "source_ids",
        ],
    }


def send_ollama_request(
    system_message: str,
    user_message: str,
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    """Send one structured request to local Ollama."""
    request_body = {
        "model": OLLAMA_MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": system_message,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "stream": False,
        "format": output_schema,
        "options": {
            "temperature": 0,
        },
        "keep_alive": "10m",
    }

    request = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(
            request_body
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            response_payload = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        details = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Ollama returned HTTP {error.code}: "
            f"{details}"
        ) from error

    except (
        urllib.error.URLError,
        TimeoutError,
    ) as error:
        raise RuntimeError(
            "The request to Ollama failed."
        ) from error

    message = response_payload.get(
        "message",
        {},
    )

    content = str(
        message.get("content", "")
    ).strip()

    if not content:
        raise RuntimeError(
            "Qwen returned an empty response."
        )

    try:
        return json.loads(content)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Qwen did not return valid structured JSON."
        ) from error


def call_qwen_with_verified_evidence(
    question: str,
    context: str,
) -> dict[str, Any]:
    """
    Generate an answer when exact control evidence is verified.

    Qwen is not asked to make another answerability decision.
    """
    system_message = """
You are a grounded question-answering assistant for the
CIS Controls v8 document.

The application has already verified that the supplied sources
directly answer the question.

Rules:
1. Answer the question using only the supplied sources.
2. Do not use outside or remembered knowledge.
3. Do not claim that information is missing.
4. Do not refuse the question.
5. For a question asking what a CIS Control is, begin with the
   main overview in Source 1.
6. Write a clear and concise explanation.
7. Cite every factual paragraph using [Source N].
8. Include only the source IDs that directly support the answer.
9. Never invent a source number.
""".strip()

    user_message = f"""
Question:
{question}

The evidence has already been verified by matching the requested
CIS Control number against document metadata.

Retrieved sources:
{context}
""".strip()

    return send_ollama_request(
        system_message=system_message,
        user_message=user_message,
        output_schema=verified_response_schema(),
    )


def call_qwen_with_evidence_check(
    question: str,
    context: str,
) -> dict[str, Any]:
    """Handle general questions without an exact Control match."""
    system_message = f"""
You are a grounded question-answering assistant for the
CIS Controls v8 document.

Rules:
1. Use only the supplied retrieved sources.
2. Do not use outside or remembered knowledge.
3. Do not invent missing facts.
4. Set answerable to true only when the sources directly answer
   the question.
5. When answerable is true, provide a concise answer and cite
   supporting passages using [Source N].
6. Include only source numbers that directly support the answer.
7. When evidence is insufficient, set answerable to false and
   return this exact answer:
   {REFUSAL_MESSAGE}
""".strip()

    user_message = f"""
Question:
{question}

Retrieved sources:
{context}
""".strip()

    return send_ollama_request(
        system_message=system_message,
        user_message=user_message,
        output_schema=unverified_response_schema(),
    )


def normalize_source_ids(
    raw_source_ids: Any,
    available_sources: list[Source],
) -> list[Source]:
    """Validate source IDs returned by Qwen."""
    if not isinstance(raw_source_ids, list):
        return []

    valid_source_ids = {
        source.source_id
        for source in available_sources
    }

    normalized_ids: set[int] = set()

    for raw_source_id in raw_source_ids:
        if isinstance(raw_source_id, bool):
            continue

        try:
            source_id = int(raw_source_id)
        except (TypeError, ValueError):
            continue

        if source_id in valid_source_ids:
            normalized_ids.add(source_id)

    return [
        source
        for source in available_sources
        if source.source_id in normalized_ids
    ]


def normalize_verified_answer(
    model_response: dict[str, Any],
    available_sources: list[Source],
) -> GeneratedAnswer:
    """Validate an answer generated from verified evidence."""
    answer = str(
        model_response.get("answer", "")
    ).strip()

    cited_sources = normalize_source_ids(
        model_response.get("source_ids", []),
        available_sources,
    )

    if not answer or not cited_sources:
        return GeneratedAnswer(
            answer=REFUSAL_MESSAGE,
            sources=[],
        )

    return GeneratedAnswer(
        answer=answer,
        sources=cited_sources,
    )


def normalize_unverified_answer(
    model_response: dict[str, Any],
    available_sources: list[Source],
) -> GeneratedAnswer:
    """Validate a response for a general question."""
    if model_response.get("answerable") is not True:
        return GeneratedAnswer(
            answer=REFUSAL_MESSAGE,
            sources=[],
        )

    answer = str(
        model_response.get("answer", "")
    ).strip()

    cited_sources = normalize_source_ids(
        model_response.get("source_ids", []),
        available_sources,
    )

    if not answer or not cited_sources:
        return GeneratedAnswer(
            answer=REFUSAL_MESSAGE,
            sources=[],
        )

    return GeneratedAnswer(
        answer=answer,
        sources=cited_sources,
    )


def print_context_sources(
    candidates: list[RetrievalCandidate],
) -> None:
    """Print the source order sent to Qwen."""
    print("\nContext sources sent to Qwen:")

    for source_id, candidate in enumerate(
        candidates,
        start=1,
    ):
        properties = candidate.properties

        print(
            f"- Source {source_id}: "
            f"Pages {format_page_range(properties)} | "
            f"{properties.get('section_title')}"
        )


def answer_question(
    question: str,
) -> GeneratedAnswer:
    """Run retrieval, reranking and grounded generation."""
    cleaned_question = validate_query(
        question
    )

    check_ollama()

    print("Loading embedding model...")
    embedding_model = create_embedding_model()

    print("Loading reranker...")
    reranker = create_reranker()

    print("Connecting to Weaviate...")
    client = connect_to_weaviate()

    try:
        print("Retrieving candidate chunks...")

        candidates = retrieve_candidates(
            client=client,
            embedding_model=embedding_model,
            query=cleaned_question,
            candidate_count=DEFAULT_CANDIDATE_COUNT,
        )

        print(
            f"Candidates retrieved: "
            f"{len(candidates)}"
        )

        print("Reranking candidates...")

        reranked_candidates = rerank_candidates(
            reranker=reranker,
            query=cleaned_question,
            candidates=candidates,
            final_count=DEFAULT_FINAL_COUNT,
        )

        ordered_candidates = order_context_candidates(
            cleaned_question,
            reranked_candidates,
        )

        print_context_sources(
            ordered_candidates
        )

        context = build_context(
            ordered_candidates
        )

        available_sources = build_sources(
            ordered_candidates
        )

        verified_evidence = (
            has_verified_control_evidence(
                cleaned_question,
                ordered_candidates,
            )
        )

        if verified_evidence:
            print(
                "\nExact Control evidence verified "
                "using metadata."
            )

            print(
                f"Generating grounded answer with "
                f"{OLLAMA_MODEL_NAME}..."
            )

            model_response = (
                call_qwen_with_verified_evidence(
                    question=cleaned_question,
                    context=context,
                )
            )

            print("\nRaw Qwen response:")
            print(
                json.dumps(
                    model_response,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            return normalize_verified_answer(
                model_response=model_response,
                available_sources=available_sources,
            )

        print(
            "\nNo exact Control metadata verification. "
            "Qwen will check the retrieved evidence."
        )

        model_response = (
            call_qwen_with_evidence_check(
                question=cleaned_question,
                context=context,
            )
        )

        print("\nRaw Qwen response:")
        print(
            json.dumps(
                model_response,
                ensure_ascii=False,
                indent=2,
            )
        )

        return normalize_unverified_answer(
            model_response=model_response,
            available_sources=available_sources,
        )

    finally:
        client.close()


def print_answer(
    generated_answer: GeneratedAnswer,
) -> None:
    """Print the final answer and validated citations."""
    print("\nAnswer:")
    print(generated_answer.answer)

    if not generated_answer.sources:
        print("\nSources: none")
        return

    print("\nSources:")

    for source in generated_answer.sources:
        if (
            source.end_page_number is None
            or source.end_page_number
            == source.page_number
        ):
            pages = str(source.page_number)
        else:
            pages = (
                f"{source.page_number}-"
                f"{source.end_page_number}"
            )

        print(
            f"- [Source {source.source_id}] "
            f"Pages {pages}: "
            f"{source.section_title}"
        )


def parse_arguments() -> argparse.Namespace:
    """Read the question from the command line."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate a grounded answer from the "
            "local CIS Controls RAG pipeline."
        )
    )

    parser.add_argument(
        "--query",
        default="What is CIS Control 1?",
        help="Question to answer.",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    generated_answer = answer_question(
        arguments.query
    )

    print_answer(
        generated_answer
    )


if __name__ == "__main__":
    main()