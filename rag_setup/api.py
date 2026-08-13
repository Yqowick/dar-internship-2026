from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from chat_models import (
    ConversationDetailResponse,
    ConversationListResponse,
    DeleteConversationResponse,
    FeedbackLookupResponse,
    FeedbackResponse,
    FeedbackUpsertRequest,
    RegenerateRequest,
    ResponseVersionListResponse,
    StoredMessageResponse,
)
from chat_repository import ChatRepository
from embedding import create_embedding_model
from generation import (
    OLLAMA_CHAT_URL,
    OLLAMA_MODEL_NAME,
    REFUSAL_MESSAGE,
    GeneratedAnswer,
    Source,
    build_context,
    build_sources,
    call_qwen_with_evidence_check,
    call_qwen_with_verified_evidence,
    check_ollama,
    has_verified_control_evidence,
    normalize_unverified_answer,
    normalize_verified_answer,
    order_context_candidates,
)
from retrieval import (
    DEFAULT_CANDIDATE_COUNT,
    DEFAULT_FINAL_COUNT,
    create_reranker,
    rerank_candidates,
    retrieve_candidates,
    validate_query,
)
from mongo_database import mongo_database
from mongo_schema import initialize_mongo_schema
from vector_store import connect_to_weaviate


API_TITLE = "CIS Controls Local RAG API"
API_VERSION = "1.6.0"

WORD_DELAY_SECONDS = 0.015
OLLAMA_TIMEOUT_SECONDS = 300.0


class AskRequest(BaseModel):
    """Question submitted by the frontend."""

    question: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        examples=["What is CIS Control 1?"],
    )
    client_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description=(
            "Anonymous browser identifier used for MongoDB chat history."
        ),
    )
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Existing MongoDB conversation identifier when resuming a chat."
        ),
    )


class SourceResponse(BaseModel):
    """One document source supporting the answer."""

    source_id: int
    chunk_id: str
    source_document: str
    section_title: str
    page_number: int | None
    end_page_number: int | None
    snippet: str | None = None


class AskResponse(BaseModel):
    """Grounded answer returned to the frontend."""

    answer: str
    refused: bool
    sources: list[SourceResponse]


class HealthResponse(BaseModel):
    """Health state of the local RAG and persistence services."""

    status: str
    api: bool
    weaviate: bool
    mongodb: bool
    ollama: bool
    models_loaded: bool


@dataclass
class PreparedQuestion:
    """Retrieved and reranked evidence prepared for generation."""

    question: str
    context: str
    sources: list[Source]
    source_snippets: dict[int, str]
    verified_evidence: bool


@dataclass
class PersistedTurn:
    """MongoDB target used to persist an initial or regenerated answer."""

    client_id: str
    conversation_id: str
    assistant_message_id: str
    mode: str = "initial"
    initial_event: str | None = "conversation"
    initial_payload: dict[str, Any] | None = None


@dataclass
class StreamState:
    """Final stream content that must be persisted once."""

    content: str = ""
    sources: list[dict[str, Any]] = field(
        default_factory=list
    )
    refused: bool = False
    status: str = "streaming"


@dataclass
class RAGRuntime:
    """
    Long-lived RAG resources.

    The embedding model and reranker are loaded once during API startup
    and reused for every question.
    """

    embedding_model: object
    reranker: object
    weaviate_client: object
    inference_lock: asyncio.Lock

    def retrieve(self, question: str):
        """Validate a question and retrieve candidate chunks."""
        cleaned_question = validate_query(question)

        candidates = retrieve_candidates(
            client=self.weaviate_client,
            embedding_model=self.embedding_model,
            query=cleaned_question,
            candidate_count=DEFAULT_CANDIDATE_COUNT,
        )

        return cleaned_question, candidates

    def rerank(self, question: str, candidates):
        """Rerank candidates and prepare final generation evidence."""
        reranked_candidates = rerank_candidates(
            reranker=self.reranker,
            query=question,
            candidates=candidates,
            final_count=DEFAULT_FINAL_COUNT,
        )

        ordered_candidates = order_context_candidates(
            question,
            reranked_candidates,
        )

        sources = build_sources(
            ordered_candidates
        )

        return PreparedQuestion(
            question=question,
            context=build_context(ordered_candidates),
            sources=sources,
            source_snippets=build_source_snippets(
                ordered_candidates,
                sources,
            ),
            verified_evidence=has_verified_control_evidence(
                question,
                ordered_candidates,
            ),
        )

    def answer(self, question: str) -> GeneratedAnswer:
        """Run the existing non-streaming RAG pipeline."""
        cleaned_question, candidates = self.retrieve(question)
        prepared = self.rerank(cleaned_question, candidates)

        if prepared.verified_evidence:
            model_response = call_qwen_with_verified_evidence(
                question=prepared.question,
                context=prepared.context,
            )

            return normalize_verified_answer(
                model_response=model_response,
                available_sources=prepared.sources,
            )

        model_response = call_qwen_with_evidence_check(
            question=prepared.question,
            context=prepared.context,
        )

        return normalize_unverified_answer(
            model_response=model_response,
            available_sources=prepared.sources,
        )


def get_runtime(request: Request) -> RAGRuntime:
    """Return the initialized runtime stored on the FastAPI app."""
    runtime = getattr(
        request.app.state,
        "rag_runtime",
        None,
    )

    if runtime is None:
        raise HTTPException(
            status_code=503,
            detail="The RAG service is not initialized.",
        )

    return runtime


def get_chat_repository(
    request: Request,
) -> ChatRepository:
    """Return the initialized MongoDB chat repository."""
    repository = getattr(
        request.app.state,
        "chat_repository",
        None,
    )

    if repository is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB chat persistence is not initialized.",
        )

    return repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load shared RAG and database resources once.

    The embedding model, reranker, Weaviate client, and MongoDB client
    are reused for all requests and closed cleanly during shutdown.
    """
    weaviate_client = None
    mongodb_connected = False

    try:
        print("Starting CIS Controls RAG API...")
        print("Checking Ollama and qwen2.5:3b...")
        check_ollama()

        print("Loading embedding model once...")
        embedding_model = create_embedding_model()

        print("Loading reranker once...")
        reranker = create_reranker()

        print("Connecting to Weaviate...")
        weaviate_client = connect_to_weaviate()

        print("Connecting to MongoDB...")
        await mongo_database.connect()
        mongodb_connected = True

        if mongo_database.database is None:
            raise RuntimeError(
                "MongoDB database was not initialized."
            )

        print("Checking MongoDB collections and indexes...")
        await initialize_mongo_schema(
            mongo_database.database
        )

        app.state.rag_runtime = RAGRuntime(
            embedding_model=embedding_model,
            reranker=reranker,
            weaviate_client=weaviate_client,
            inference_lock=asyncio.Lock(),
        )

        app.state.mongo_database = (
            mongo_database.database
        )
        app.state.chat_repository = ChatRepository(
            mongo_database.database
        )

        print("CIS Controls RAG API is ready.")

        yield

    finally:
        print("Stopping CIS Controls RAG API...")

        runtime = getattr(
            app.state,
            "rag_runtime",
            None,
        )

        if runtime is not None:
            runtime.weaviate_client.close()
        elif weaviate_client is not None:
            weaviate_client.close()

        app.state.rag_runtime = None
        app.state.chat_repository = None
        app.state.mongo_database = None

        if mongodb_connected:
            await mongo_database.close()


app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=(
        "Local retrieval-augmented generation API grounded only "
        "in the CIS Controls v8 document."
    ),
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Accept",
        "Content-Type",
    ],
)


def _candidate_value(
    candidate: Any,
    field_name: str,
) -> Any:
    """Read a value from common retrieval-candidate shapes."""
    direct_value = getattr(
        candidate,
        field_name,
        None,
    )

    if direct_value is not None:
        return direct_value

    for container_name in (
        "metadata",
        "properties",
    ):
        container = getattr(
            candidate,
            container_name,
            None,
        )

        if isinstance(container, dict):
            value = container.get(
                field_name
            )

            if value is not None:
                return value

    document = getattr(
        candidate,
        "document",
        None,
    )

    if document is not None:
        direct_document_value = getattr(
            document,
            field_name,
            None,
        )

        if direct_document_value is not None:
            return direct_document_value

        metadata = getattr(
            document,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            value = metadata.get(
                field_name
            )

            if value is not None:
                return value

    return None


def candidate_chunk_id(
    candidate: Any,
) -> str | None:
    """Return a candidate's stored chunk identifier when available."""
    value = _candidate_value(
        candidate,
        "chunk_id",
    )

    if value is None:
        return None

    cleaned_value = str(value).strip()

    return cleaned_value or None


def candidate_text(
    candidate: Any,
) -> str:
    """Return the retrieved chunk text from common candidate shapes."""
    for field_name in (
        "text",
        "page_content",
        "content",
    ):
        value = _candidate_value(
            candidate,
            field_name,
        )

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def create_source_snippet(
    text: str,
    section_title: str,
    maximum_characters: int = 520,
) -> str:
    """Create a compact source preview for tooltips and metadata."""
    cleaned_text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    cleaned_title = re.sub(
        r"\s+",
        " ",
        section_title,
    ).strip()

    if (
        cleaned_title
        and cleaned_text.lower().startswith(
            cleaned_title.lower()
        )
    ):
        cleaned_text = cleaned_text[
            len(cleaned_title):
        ].lstrip(" :-–—")

    if not cleaned_text:
        cleaned_text = cleaned_title

    if len(cleaned_text) <= maximum_characters:
        return cleaned_text

    shortened_text = cleaned_text[
        : maximum_characters - 1
    ].rstrip()

    last_space = shortened_text.rfind(
        " "
    )

    if last_space >= 280:
        shortened_text = shortened_text[
            :last_space
        ]

    return f"{shortened_text}…"


def build_source_snippets(
    ordered_candidates: list[Any],
    sources: list[Source],
) -> dict[int, str]:
    """Match each public source number to a retrieved-text preview."""
    candidates_by_chunk_id: dict[
        str,
        Any,
    ] = {}

    for candidate in ordered_candidates:
        chunk_id = candidate_chunk_id(
            candidate
        )

        if chunk_id:
            candidates_by_chunk_id[
                chunk_id
            ] = candidate

    snippets: dict[int, str] = {}

    for index, source in enumerate(
        sources
    ):
        candidate = candidates_by_chunk_id.get(
            source.chunk_id
        )

        if (
            candidate is None
            and index < len(
                ordered_candidates
            )
        ):
            candidate = ordered_candidates[
                index
            ]

        if candidate is None:
            continue

        snippet = create_source_snippet(
            candidate_text(candidate),
            source.section_title,
        )

        if snippet:
            snippets[
                source.source_id
            ] = snippet

    return snippets


def source_to_response(
    source: Source,
    snippet: str | None = None,
) -> SourceResponse:
    """Convert an internal source into an API source."""
    return SourceResponse(
        source_id=source.source_id,
        chunk_id=source.chunk_id,
        source_document=source.source_document,
        section_title=source.section_title,
        page_number=source.page_number,
        end_page_number=source.end_page_number,
        snippet=snippet,
    )


def source_to_dict(
    source: Source,
    source_snippets: dict[
        int,
        str,
    ] | None = None,
) -> dict[str, Any]:
    """Convert a source into an SSE-safe JSON object."""
    snippet = None

    if source_snippets is not None:
        snippet = source_snippets.get(
            source.source_id
        )

    return source_to_response(
        source,
        snippet=snippet,
    ).model_dump()


def make_sse_event(
    event_name: str,
    data: dict[str, Any],
) -> str:
    """Serialize one Server-Sent Event."""
    payload = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return (
        f"event: {event_name}\n"
        f"data: {payload}\n\n"
    )


def pop_complete_words(
    buffer: str,
) -> tuple[list[str], str]:
    """
    Return complete words with their following whitespace.

    Keeping whitespace preserves Markdown paragraphs and lists.
    """
    words: list[str] = []
    last_end = 0

    for match in re.finditer(
        r"\S+\s+",
        buffer,
    ):
        words.append(match.group(0))
        last_end = match.end()

    return words, buffer[last_end:]


def cited_sources(
    answer: str,
    available_sources: list[Source],
) -> list[Source]:
    """Keep model-cited sources, falling back to prepared evidence."""
    cited_ids = {
        int(match)
        for match in re.findall(
            r"\[(?:Source\s+)?(\d+)\]",
            answer,
            flags=re.IGNORECASE,
        )
    }

    selected_sources = [
        source
        for source in available_sources
        if source.source_id in cited_ids
    ]

    return selected_sources or available_sources


def build_answerability_messages(
    prepared: PreparedQuestion,
) -> tuple[str, str]:
    """Build a small evidence-classification request."""
    system_message = f"""
You are an evidence classifier for a CIS Controls v8 RAG system.

Rules:
1. Decide only whether the supplied sources directly contain enough
   information to answer the user's question.
2. Use only the supplied sources.
3. Do not answer the question.
4. Do not use outside knowledge.
5. Return answerable=false for unrelated questions.
6. A partial keyword match is not enough.
7. The refusal used by the application is:
   {REFUSAL_MESSAGE}
""".strip()

    user_message = f"""
Question:
{prepared.question}

Retrieved sources:
{prepared.context}
""".strip()

    return system_message, user_message


def build_streaming_answer_messages(
    prepared: PreparedQuestion,
    is_regeneration: bool = False,
) -> tuple[str, str]:
    """Build a grounded answer prompt for an initial or regenerated reply."""
    regeneration_rule = (
        "10. Produce a fresh alternative formulation while preserving the "
        "same grounded meaning and citation accuracy."
        if is_regeneration
        else ""
    )

    system_message = f"""
You are a grounded question-answering assistant for the CIS Controls v8 document.

The application has already verified that the supplied sources contain
enough evidence to answer the question.

Rules:
1. Answer using only the supplied sources.
2. Do not use outside or remembered knowledge.
3. Do not refuse the question.
4. Keep the answer focused and readable.
5. Use Markdown when it improves clarity.
6. Cite factual paragraphs with inline numeric citations such as [1] or [2].
7. Each citation number must match the corresponding retrieved Source number.
8. Never invent a source number.
9. For a question asking what a CIS Control is, begin with its main overview.
{regeneration_rule}
""".strip()

    user_message = f"""
Question:
{prepared.question}

Retrieved sources:
{prepared.context}
""".strip()

    return system_message, user_message


async def check_answerability(
    prepared: PreparedQuestion,
) -> bool:
    """
    Verify answerability before streaming.

    Exact CIS Control metadata matches bypass this extra model call.
    General questions use a tiny structured classification request.
    """
    if prepared.verified_evidence:
        return True

    system_message, user_message = build_answerability_messages(
        prepared
    )

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
        "format": {
            "type": "object",
            "properties": {
                "answerable": {
                    "type": "boolean",
                },
            },
            "required": [
                "answerable",
            ],
        },
        "options": {
            "temperature": 0,
            "num_predict": 24,
        },
        "keep_alive": "10m",
    }

    timeout = httpx.Timeout(
        connect=15.0,
        read=OLLAMA_TIMEOUT_SECONDS,
        write=30.0,
        pool=15.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
    ) as client:
        response = await client.post(
            OLLAMA_CHAT_URL,
            json=request_body,
        )

        response.raise_for_status()
        response_payload = response.json()

    content = str(
        response_payload.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )
    ).strip()

    if not content:
        raise RuntimeError(
            "Qwen returned an empty evidence decision."
        )

    try:
        decision = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Qwen returned an invalid evidence decision."
        ) from error

    return decision.get("answerable") is True


async def iter_ollama_content(
    system_message: str,
    user_message: str,
    temperature: float = 0.0,
) -> AsyncIterator[str]:
    """Yield content fragments from Ollama's streaming chat API."""
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
        "stream": True,
        "options": {
            "temperature": temperature,
        },
        "keep_alive": "10m",
    }

    timeout = httpx.Timeout(
        connect=15.0,
        read=OLLAMA_TIMEOUT_SECONDS,
        write=30.0,
        pool=15.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
    ) as client:
        async with client.stream(
            "POST",
            OLLAMA_CHAT_URL,
            json=request_body,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                payload = json.loads(line)

                if payload.get("error"):
                    raise RuntimeError(
                        str(payload["error"])
                    )

                content = str(
                    payload.get(
                        "message",
                        {},
                    ).get(
                        "content",
                        "",
                    )
                )

                if content:
                    yield content

                if payload.get("done") is True:
                    break


async def stream_text_as_words(
    text: str,
    request: Request,
) -> AsyncIterator[str]:
    """Stream prepared text as one visible word per SSE event."""
    buffer = f"{text.strip()} "

    words, remainder = pop_complete_words(buffer)

    for word in words:
        if await request.is_disconnected():
            return

        yield make_sse_event(
            "token",
            {
                "text": word,
            },
        )

        await asyncio.sleep(
            WORD_DELAY_SECONDS
        )

    if remainder:
        yield make_sse_event(
            "token",
            {
                "text": remainder,
            },
        )


async def stream_grounded_answer(
    prepared: PreparedQuestion,
    request: Request,
    stream_state: StreamState,
    is_regeneration: bool = False,
) -> AsyncIterator[str]:
    """Stream a verified Qwen answer and capture its final state."""
    system_message, user_message = build_streaming_answer_messages(
        prepared,
        is_regeneration=is_regeneration,
    )

    answer_buffer = ""
    full_answer = ""

    async for content_fragment in iter_ollama_content(
        system_message,
        user_message,
        temperature=(0.35 if is_regeneration else 0.0),
    ):
        if await request.is_disconnected():
            stream_state.content = full_answer + answer_buffer
            stream_state.status = "stopped"
            return

        answer_buffer += content_fragment

        words, answer_buffer = pop_complete_words(
            answer_buffer
        )

        for word in words:
            if await request.is_disconnected():
                stream_state.content = full_answer + answer_buffer
                stream_state.status = "stopped"
                return

            full_answer += word
            stream_state.content = full_answer

            yield make_sse_event(
                "token",
                {
                    "text": word,
                },
            )

            await asyncio.sleep(
                WORD_DELAY_SECONDS
            )

    if answer_buffer:
        full_answer += answer_buffer
        stream_state.content = full_answer

        yield make_sse_event(
            "token",
            {
                "text": answer_buffer,
            },
        )

    if not full_answer.strip():
        raise RuntimeError(
            "Qwen returned an empty streamed answer."
        )

    stream_state.content = full_answer.strip()
    stream_state.refused = (
        stream_state.content == REFUSAL_MESSAGE
    )

    final_sources = (
        []
        if stream_state.refused
        else cited_sources(
            full_answer,
            prepared.sources,
        )
    )

    stream_state.sources = [
        source_to_dict(
            source,
            prepared.source_snippets,
        )
        for source in final_sources
    ]
    stream_state.status = "complete"

    yield make_sse_event(
        "sources",
        {
            "sources": stream_state.sources,
        },
    )


async def persist_stream_state(
    repository: ChatRepository,
    turn: PersistedTurn,
    stream_state: StreamState,
) -> dict[str, Any]:
    """Persist an initial or regenerated stream, including cancellations."""
    persistence_method = (
        repository.finish_regeneration
        if turn.mode == "regeneration"
        else repository.finish_assistant_message
    )
    persistence_task = asyncio.create_task(
        persistence_method(
            client_id=turn.client_id,
            conversation_id=turn.conversation_id,
            assistant_message_id=turn.assistant_message_id,
            content=stream_state.content,
            status=stream_state.status,
            refused=stream_state.refused,
            sources=stream_state.sources,
        )
    )

    try:
        return await asyncio.shield(
            persistence_task
        )
    except asyncio.CancelledError:
        await persistence_task
        raise


async def rag_stream(
    runtime: RAGRuntime,
    question: str,
    request: Request,
    repository: ChatRepository | None = None,
    turn: PersistedTurn | None = None,
    is_regeneration: bool = False,
) -> AsyncIterator[str]:
    """Run the RAG pipeline and persist the complete streamed turn."""
    stream_state = StreamState()
    persisted = False

    try:
        if (
            turn is not None
            and turn.initial_event is not None
            and turn.initial_payload is not None
        ):
            yield make_sse_event(
                turn.initial_event,
                turn.initial_payload,
            )

        async with runtime.inference_lock:
            if await request.is_disconnected():
                stream_state.status = "stopped"
                return

            yield make_sse_event(
                "status",
                {
                    "stage": "retrieving",
                    "message": "Searching the CIS document…",
                },
            )

            cleaned_question, candidates = await asyncio.to_thread(
                runtime.retrieve,
                question,
            )

            if await request.is_disconnected():
                stream_state.status = "stopped"
                return

            yield make_sse_event(
                "status",
                {
                    "stage": "reranking",
                    "message": (
                        f"Reranking {len(candidates)} "
                        "relevant sections…"
                    ),
                },
            )

            prepared = await asyncio.to_thread(
                runtime.rerank,
                cleaned_question,
                candidates,
            )

            if await request.is_disconnected():
                stream_state.status = "stopped"
                return

            if not prepared.verified_evidence:
                yield make_sse_event(
                    "status",
                    {
                        "stage": "checking",
                        "message": "Checking document evidence…",
                    },
                )

            answerable = await check_answerability(
                prepared
            )

            if await request.is_disconnected():
                stream_state.status = "stopped"
                return

            if not answerable:
                stream_state.content = REFUSAL_MESSAGE
                stream_state.refused = True
                stream_state.sources = []

                async for event in stream_text_as_words(
                    REFUSAL_MESSAGE,
                    request,
                ):
                    yield event

                if await request.is_disconnected():
                    stream_state.status = "stopped"
                    return

                stream_state.status = "complete"

                yield make_sse_event(
                    "sources",
                    {
                        "sources": [],
                    },
                )
            else:
                yield make_sse_event(
                    "status",
                    {
                        "stage": "generating",
                        "message": "Generating the grounded answer…",
                    },
                )

                async for event in stream_grounded_answer(
                    prepared,
                    request,
                    stream_state,
                    is_regeneration=is_regeneration,
                ):
                    yield event

                if stream_state.status == "stopped":
                    return

        persistence_result: dict[str, Any] = {}

        if repository is not None and turn is not None:
            persistence_result = await persist_stream_state(
                repository,
                turn,
                stream_state,
            )
            persisted = True

        done_payload: dict[str, Any] = {
            "refused": stream_state.refused,
            **persistence_result,
        }

        if turn is not None:
            done_payload.update(
                {
                    "conversation_id": (
                        turn.conversation_id
                    ),
                    "assistant_message_id": (
                        turn.assistant_message_id
                    ),
                }
            )

        yield make_sse_event(
            "done",
            done_payload,
        )

    except asyncio.CancelledError:
        if stream_state.status == "streaming":
            stream_state.status = "stopped"
        raise

    except (
        ValueError,
        LookupError,
        RuntimeError,
        httpx.HTTPError,
    ) as error:
        stream_state.status = "error"
        stream_state.content = str(error)
        stream_state.sources = []

        if not await request.is_disconnected():
            yield make_sse_event(
                "error",
                {
                    "message": str(error),
                },
            )

    except Exception:
        stream_state.status = "error"
        stream_state.content = (
            "An unexpected error occurred while generating the answer."
        )
        stream_state.sources = []

        if not await request.is_disconnected():
            yield make_sse_event(
                "error",
                {
                    "message": stream_state.content,
                },
            )

    finally:
        if (
            repository is not None
            and turn is not None
            and not persisted
        ):
            if stream_state.status == "streaming":
                stream_state.status = "stopped"

            try:
                await persist_stream_state(
                    repository,
                    turn,
                    stream_state,
                )
            except Exception as error:
                print(
                    "Unable to persist streamed assistant message: "
                    f"{error}"
                )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
)
async def health(
    request: Request,
) -> HealthResponse:
    """Check the API, databases, Ollama, and loaded models."""
    runtime = get_runtime(request)

    try:
        weaviate_ready = bool(
            runtime.weaviate_client.is_ready()
        )
    except Exception:
        weaviate_ready = False

    try:
        if mongo_database.client is None:
            mongodb_ready = False
        else:
            result = await (
                mongo_database.client.admin.command(
                    "ping"
                )
            )
            mongodb_ready = result.get("ok") == 1.0
    except Exception:
        mongodb_ready = False

    try:
        check_ollama()
        ollama_ready = True
    except RuntimeError:
        ollama_ready = False

    models_loaded = (
        runtime.embedding_model is not None
        and runtime.reranker is not None
    )

    healthy = (
        weaviate_ready
        and mongodb_ready
        and ollama_ready
        and models_loaded
    )

    return HealthResponse(
        status=(
            "healthy"
            if healthy
            else "degraded"
        ),
        api=True,
        weaviate=weaviate_ready,
        mongodb=mongodb_ready,
        ollama=ollama_ready,
        models_loaded=models_loaded,
    )


@app.get(
    "/conversations",
    response_model=ConversationListResponse,
    tags=["Chat History"],
)
async def list_conversations(
    request: Request,
    client_id: str = Query(
        ...,
        min_length=8,
        max_length=128,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
) -> ConversationListResponse:
    """List persisted conversations for one anonymous browser client."""
    repository = get_chat_repository(
        request
    )

    try:
        conversations = await repository.list_conversations(
            client_id=client_id,
            limit=limit,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return ConversationListResponse(
        conversations=conversations
    )


@app.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    tags=["Chat History"],
)
async def get_conversation(
    conversation_id: str,
    request: Request,
    client_id: str = Query(
        ...,
        min_length=8,
        max_length=128,
    ),
) -> ConversationDetailResponse:
    """Load one conversation and its messages so it can be resumed."""
    repository = get_chat_repository(
        request
    )

    try:
        conversation = await repository.get_conversation(
            client_id=client_id,
            conversation_id=conversation_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return ConversationDetailResponse(
        **conversation
    )


@app.get(
    "/messages/{assistant_message_id}/versions",
    response_model=ResponseVersionListResponse,
    tags=["Response Versions"],
)
async def list_response_versions(
    assistant_message_id: str,
    request: Request,
    client_id: str = Query(
        ...,
        min_length=8,
        max_length=128,
    ),
) -> ResponseVersionListResponse:
    """List all saved alternatives for one assistant response."""
    repository = get_chat_repository(
        request
    )

    try:
        version_history = await repository.list_response_versions(
            client_id=client_id,
            assistant_message_id=assistant_message_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return ResponseVersionListResponse(
        **version_history
    )


@app.post(
    "/messages/{assistant_message_id}/versions/{version_number}/activate",
    response_model=StoredMessageResponse,
    tags=["Response Versions"],
)
async def activate_response_version(
    assistant_message_id: str,
    version_number: int,
    request: Request,
    client_id: str = Query(
        ...,
        min_length=8,
        max_length=128,
    ),
) -> StoredMessageResponse:
    """Switch the visible assistant answer to one stored version."""
    repository = get_chat_repository(
        request
    )

    try:
        message = await repository.activate_response_version(
            client_id=client_id,
            assistant_message_id=assistant_message_id,
            version_number=version_number,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return StoredMessageResponse(
        **message
    )


@app.get(
    "/messages/{assistant_message_id}/versions/{version_number}/feedback",
    response_model=FeedbackLookupResponse,
    tags=["Feedback"],
)
async def get_response_feedback(
    assistant_message_id: str,
    version_number: int,
    request: Request,
    client_id: str = Query(
        ...,
        min_length=8,
        max_length=128,
    ),
) -> FeedbackLookupResponse:
    """Load this browser's saved rating for one response version."""
    repository = get_chat_repository(
        request
    )

    try:
        feedback = await repository.get_feedback(
            client_id=client_id,
            assistant_message_id=assistant_message_id,
            version_number=version_number,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return FeedbackLookupResponse(
        feedback=(
            FeedbackResponse(**feedback)
            if feedback is not None
            else None
        )
    )


@app.put(
    "/messages/{assistant_message_id}/versions/{version_number}/feedback",
    response_model=FeedbackResponse,
    tags=["Feedback"],
)
async def save_response_feedback(
    assistant_message_id: str,
    version_number: int,
    payload: FeedbackUpsertRequest,
    request: Request,
) -> FeedbackResponse:
    """Create or update feedback for one exact response version."""
    repository = get_chat_repository(
        request
    )

    try:
        feedback = await repository.upsert_feedback(
            client_id=payload.client_id,
            assistant_message_id=assistant_message_id,
            version_number=version_number,
            rating=payload.rating,
            reason=payload.reason,
            comment=payload.comment,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return FeedbackResponse(
        **feedback
    )


@app.delete(
    "/conversations/{conversation_id}",
    response_model=DeleteConversationResponse,
    tags=["Chat History"],
)
async def delete_conversation(
    conversation_id: str,
    request: Request,
    client_id: str = Query(
        ...,
        min_length=8,
        max_length=128,
    ),
) -> DeleteConversationResponse:
    """Delete one owned conversation and all related MongoDB data."""
    repository = get_chat_repository(
        request
    )

    try:
        deleted = await repository.delete_conversation(
            client_id=client_id,
            conversation_id=conversation_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return DeleteConversationResponse(
        deleted=True,
        conversation_id=conversation_id,
    )


@app.post(
    "/ask",
    response_model=AskResponse,
    tags=["RAG"],
)
async def ask(
    payload: AskRequest,
    request: Request,
) -> AskResponse:
    """Answer one question using the non-streaming endpoint."""
    runtime = get_runtime(request)

    try:
        async with runtime.inference_lock:
            generated_answer = await asyncio.to_thread(
                runtime.answer,
                payload.question,
            )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    sources = [
        source_to_response(
            source,
            snippet=None,
        )
        for source in generated_answer.sources
    ]

    refused = (
        generated_answer.answer
        == REFUSAL_MESSAGE
        and not sources
    )

    return AskResponse(
        answer=generated_answer.answer,
        refused=refused,
        sources=sources,
    )


@app.post(
    "/messages/{assistant_message_id}/regenerate/stream",
    response_class=StreamingResponse,
    tags=["Response Versions"],
)
async def regenerate_response_stream(
    assistant_message_id: str,
    payload: RegenerateRequest,
    request: Request,
) -> StreamingResponse:
    """Generate and persist a new version of an existing assistant answer."""
    runtime = get_runtime(request)
    repository = get_chat_repository(
        request
    )

    try:
        regeneration = await repository.prepare_regeneration(
            client_id=payload.client_id,
            conversation_id=payload.conversation_id,
            assistant_message_id=assistant_message_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    turn = PersistedTurn(
        client_id=payload.client_id,
        conversation_id=payload.conversation_id,
        assistant_message_id=assistant_message_id,
        mode="regeneration",
        initial_event="regeneration",
        initial_payload={
            "assistant_message": regeneration[
                "assistant_message"
            ]
        },
    )

    return StreamingResponse(
        rag_stream(
            runtime=runtime,
            question=regeneration["question"],
            request=request,
            repository=repository,
            turn=turn,
            is_regeneration=True,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/ask/stream",
    response_class=StreamingResponse,
    tags=["RAG"],
)
async def ask_stream(
    payload: AskRequest,
    request: Request,
) -> StreamingResponse:
    """Stream a grounded answer and optionally persist the full turn."""
    runtime = get_runtime(request)
    repository: ChatRepository | None = None
    turn: PersistedTurn | None = None

    if (
        payload.conversation_id
        and not payload.client_id
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "client_id is required when conversation_id is provided."
            ),
        )

    if payload.client_id is not None:
        repository = get_chat_repository(
            request
        )

        try:
            initial_payload = await repository.start_exchange(
                client_id=payload.client_id,
                question=payload.question,
                conversation_id=(
                    payload.conversation_id
                ),
            )
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error
        except LookupError as error:
            raise HTTPException(
                status_code=404,
                detail=str(error),
            ) from error

        turn = PersistedTurn(
            client_id=payload.client_id,
            conversation_id=(
                initial_payload[
                    "conversation"
                ]["id"]
            ),
            assistant_message_id=(
                initial_payload[
                    "assistant_message"
                ]["id"]
            ),
            mode="initial",
            initial_event="conversation",
            initial_payload=initial_payload,
        )

    return StreamingResponse(
        rag_stream(
            runtime=runtime,
            question=payload.question,
            request=request,
            repository=repository,
            turn=turn,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
