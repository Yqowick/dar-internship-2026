from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from embedding import create_embedding_model
from generation import (
    REFUSAL_MESSAGE,
    GeneratedAnswer,
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
from vector_store import connect_to_weaviate


API_TITLE = "CIS Controls Local RAG API"
API_VERSION = "1.0.0"


class AskRequest(BaseModel):
    """Question submitted by the frontend."""

    question: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        examples=["What is CIS Control 1?"],
    )


class SourceResponse(BaseModel):
    """One document source supporting the answer."""

    source_id: int
    chunk_id: str
    source_document: str
    section_title: str
    page_number: int | None
    end_page_number: int | None


class AskResponse(BaseModel):
    """Grounded answer returned to the frontend."""

    answer: str
    refused: bool
    sources: list[SourceResponse]


class HealthResponse(BaseModel):
    """Health state of the local RAG services."""

    status: str
    api: bool
    weaviate: bool
    ollama: bool
    models_loaded: bool


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
    inference_lock: Lock

    def answer(self, question: str) -> GeneratedAnswer:
        """Run the complete RAG pipeline for one question."""
        cleaned_question = validate_query(question)

        candidates = retrieve_candidates(
            client=self.weaviate_client,
            embedding_model=self.embedding_model,
            query=cleaned_question,
            candidate_count=DEFAULT_CANDIDATE_COUNT,
        )

        reranked_candidates = rerank_candidates(
            reranker=self.reranker,
            query=cleaned_question,
            candidates=candidates,
            final_count=DEFAULT_FINAL_COUNT,
        )

        ordered_candidates = order_context_candidates(
            cleaned_question,
            reranked_candidates,
        )

        context = build_context(ordered_candidates)
        available_sources = build_sources(ordered_candidates)

        if has_verified_control_evidence(
            cleaned_question,
            ordered_candidates,
        ):
            model_response = call_qwen_with_verified_evidence(
                question=cleaned_question,
                context=context,
            )

            return normalize_verified_answer(
                model_response=model_response,
                available_sources=available_sources,
            )

        model_response = call_qwen_with_evidence_check(
            question=cleaned_question,
            context=context,
        )

        return normalize_unverified_answer(
            model_response=model_response,
            available_sources=available_sources,
        )


def get_runtime(request: Request) -> RAGRuntime:
    """Return the initialized runtime stored on the FastAPI app."""
    runtime = getattr(request.app.state, "rag_runtime", None)

    if runtime is None:
        raise HTTPException(
            status_code=503,
            detail="The RAG service is not initialized.",
        )

    return runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load shared RAG resources once and release them on shutdown."""
    print("Starting CIS Controls RAG API...")
    print("Checking Ollama and qwen2.5:3b...")
    check_ollama()

    print("Loading embedding model once...")
    embedding_model = create_embedding_model()

    print("Loading reranker once...")
    reranker = create_reranker()

    print("Connecting to Weaviate...")
    weaviate_client = connect_to_weaviate()

    app.state.rag_runtime = RAGRuntime(
        embedding_model=embedding_model,
        reranker=reranker,
        weaviate_client=weaviate_client,
        inference_lock=Lock(),
    )

    print("CIS Controls RAG API is ready.")

    try:
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

        app.state.rag_runtime = None


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
        "OPTIONS",
    ],
    allow_headers=[
        "Content-Type",
    ],
)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
)
def health(request: Request) -> HealthResponse:
    """Check the API, Weaviate, Ollama, and loaded models."""
    runtime = get_runtime(request)

    try:
        weaviate_ready = bool(
            runtime.weaviate_client.is_ready()
        )
    except Exception:
        weaviate_ready = False

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
        and ollama_ready
        and models_loaded
    )

    return HealthResponse(
        status="healthy" if healthy else "degraded",
        api=True,
        weaviate=weaviate_ready,
        ollama=ollama_ready,
        models_loaded=models_loaded,
    )


@app.post(
    "/ask",
    response_model=AskResponse,
    tags=["RAG"],
)
def ask(
    payload: AskRequest,
    request: Request,
) -> AskResponse:
    """Answer one question using only evidence from the CIS PDF."""
    runtime = get_runtime(request)

    try:
        with runtime.inference_lock:
            generated_answer = runtime.answer(
                payload.question
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
        SourceResponse(
            source_id=source.source_id,
            chunk_id=source.chunk_id,
            source_document=source.source_document,
            section_title=source.section_title,
            page_number=source.page_number,
            end_page_number=source.end_page_number,
        )
        for source in generated_answer.sources
    ]

    refused = (
        generated_answer.answer == REFUSAL_MESSAGE
        and not sources
    )

    return AskResponse(
        answer=generated_answer.answer,
        refused=refused,
        sources=sources,
    )