# CIS Controls v8 Local RAG - GitHub Copilot Instructions

## Purpose of this artifact

This file customizes GitHub Copilot for the repository. It records the project's architecture, non-negotiable grounding rules, coding conventions, and delivery workflow so AI-generated suggestions remain consistent with the implemented system.

## Project purpose

Build and maintain a fully local Retrieval-Augmented Generation assistant grounded only in the CIS Controls v8 PDF.

The assistant must refuse unsupported questions with exactly:

`The retrieved documents do not contain enough information to answer this question.`

Do not weaken, paraphrase, or bypass this refusal rule.

## Current architecture

- Parsing: Unstructured `hi_res`, Poppler, Tesseract
- Chunking: control-aware semantic sections, approximately 155 chunks across all 18 controls
- Embeddings: `BAAI/bge-small-en-v1.5`
- Vector store: local Weaviate in Docker
- Retrieval: hybrid search, around 20 candidates
- Reranking: `BAAI/bge-reranker-v2-m3`, retain best 5
- Generator: Ollama `qwen2.5:3b`
- Backend: Python 3.12+, FastAPI, Pydantic, Server-Sent Events
- Persistence: MongoDB 8 in Docker
- Frontend: React, TypeScript, Vite, Tailwind CSS v4, shadcn/ui
- Markdown: `react-markdown` and `remark-gfm`

## Grounding and RAG rules

- Never answer from outside knowledge.
- Never skip retrieval or reranking.
- Preserve source document, page range, section title, control number, control title, chunk ID, and source snippet.
- Keep retrieval and generation behavior deterministic where practical.
- Load the embedding model and reranker once during FastAPI startup.
- Keep the existing `/ask` endpoint and SSE `/ask/stream` endpoint.
- Citations in the answer must map to sources returned by the backend.
- Unsupported questions must return the exact refusal message and no invented citations.

## Backend organization

- `clean_pdf.py`: high-resolution parsing and cache
- `chunking.py`: natural boundaries, token limits, overlap, and metadata
- `embedding.py`: local normalized embeddings
- `vector_store.py`: Weaviate collection and ingestion
- `retrieval.py`: candidate search and reranking
- `generation.py`: context building, Qwen calls, normalization, refusal
- `api.py`: FastAPI routes, SSE, service lifecycle, CORS
- `mongo_database.py`: async MongoDB connection lifecycle
- `mongo_schema.py`: collections and indexes
- `chat_models.py`: request and response models
- `chat_repository.py`: conversations, messages, versions, feedback

## Persistence rules

MongoDB is the source of truth for chat data:

- `conversations`
- `messages`
- `response_versions`
- `feedback`

The browser may store only:

- anonymous `client_id`
- guided-tour completion flag

Do not move full chat history back to browser `localStorage`.

A new conversation should be persisted only after the first question is sent. Feedback is linked to one exact response version and should be idempotently updated rather than duplicated.

## Frontend rules

- Keep TypeScript strict mode.
- Keep chat components in `src/components/chat`.
- Keep shared UI primitives in `src/components/ui`.
- Keep backend calls in `src/services`.
- Keep shared models in `src/types`.
- Read the backend URL from `VITE_RAG_API_URL`.
- Preserve welcome, empty, loading, retrieving, reranking, generating, streaming, stopped, refusal, and error states.
- Use React Markdown for assistant content.
- Use `AbortController` for stop generation.
- Keep citations clickable and connected to source metadata.
- Preserve response versions and version-specific feedback.
- Preserve the first-time guided tour and replay control.
- Maintain keyboard accessibility and responsive behavior.
- Do not hardcode answers, citations, database IDs, or local machine paths.

## API behavior to preserve

- `GET /health`
- `POST /ask`
- `POST /ask/stream`
- `GET /conversations`
- `GET /conversations/{conversation_id}`
- `DELETE /conversations/{conversation_id}`
- `POST /messages/{assistant_message_id}/regenerate/stream`
- `GET /messages/{assistant_message_id}/versions`
- `POST /messages/{assistant_message_id}/versions/{version_number}/activate`
- `GET /messages/{assistant_message_id}/versions/{version_number}/feedback`
- `PUT /messages/{assistant_message_id}/versions/{version_number}/feedback`

## Code quality rules

- Prefer small, typed functions and descriptive names.
- Add comments for non-obvious RAG, SSE, and persistence decisions; do not comment trivial syntax.
- Validate external input and convert internal exceptions into useful HTTP errors.
- Close Weaviate and MongoDB connections during application shutdown.
- Avoid blocking the event loop; run CPU-bound inference in a worker thread when appropriate.
- Keep secrets in `.env`, provide placeholders in `.env.example`, and never print passwords.

## Git workflow

- Work only on feature branches.
- Do not merge directly to `main`.
- Use descriptive commits.
- Review `git status --short` before committing.
- Do not commit `.env`, caches, virtual environments, `node_modules`, `dist`, models, or temporary parsing files.
- Open and self-review a pull request against `main`.

## AI tooling usage and impact

GitHub Copilot is used for scoped implementation suggestions, refactoring, comments, and consistency checks. The instructions in this file reduce hallucinated architecture changes and prevent regressions such as bypassing retrieval, replacing MongoDB with browser storage, weakening the refusal rule, or hardcoding citations.

All AI-generated changes must be read, executed locally, and reviewed before commit. AI assists development; it does not replace developer responsibility.
