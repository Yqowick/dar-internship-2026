# CIS Controls v8 Local RAG Assistant - Setup Guide

This folder contains the complete local application: ingestion, retrieval, reranking, generation, FastAPI, MongoDB persistence, and the React frontend.

## 1. Prerequisites

- Python 3.12 or newer
- `uv`
- Node.js 20 or newer and npm
- Docker Desktop
- Ollama
- Poppler and Tesseract only when parsing the PDF from scratch

The first model download and high-resolution PDF parsing are one-time operations and may take several minutes on CPU.

## 2. Configure the environment

From `rag_setup`:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and replace the placeholder values:

```env
MONGO_INITDB_ROOT_USERNAME=your_local_username
MONGO_INITDB_ROOT_PASSWORD=your_local_password
MONGO_DATABASE=cis_rag
MONGODB_URL=mongodb://your_local_username:your_local_password@127.0.0.1:27017/cis_rag?authSource=admin
```

Never commit `.env`.

## 3. Start Weaviate and MongoDB

```powershell
docker compose up -d
docker compose ps
```

Local ports:

- Weaviate HTTP: `127.0.0.1:8080`
- Weaviate gRPC: `127.0.0.1:50051`
- MongoDB: `127.0.0.1:27017`

Data is stored in persistent Docker volumes.

## 4. Prepare Ollama

```powershell
ollama pull qwen2.5:3b
ollama list
```

Keep the Ollama service running.

## 5. Install backend dependencies

```powershell
uv sync
```

The lock file pins the dependency versions used by the project.

## 6. Build the vector collection (first run only)

```powershell
uv run python vector_store.py
```

This command parses the CIS Controls v8 PDF, creates meaningful chunks, embeds them with `BAAI/bge-small-en-v1.5`, and stores the vectors and metadata in Weaviate.

The current pipeline produces approximately 155 chunks covering all 18 controls. Metadata includes source document, page range, section title, control number, control title, and chunk ID.

## 7. Start the FastAPI backend

```powershell
uv run uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

Useful URLs:

- Health: `http://127.0.0.1:8000/health`
- OpenAPI: `http://127.0.0.1:8000/docs`

At startup, the API loads the embedding model and reranker once, connects to Weaviate and MongoDB, validates Ollama, and creates required MongoDB indexes.

## 8. Start the frontend

Open another PowerShell terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Frontend environment:

```env
VITE_RAG_API_URL=http://127.0.0.1:8000
```

Open `http://localhost:5173`.

## 9. Application flow

```text
Question
-> query embedding
-> Weaviate hybrid retrieval (around 20 chunks)
-> BGE reranking
-> best 5 chunks
-> grounded Qwen prompt
-> streamed answer and citations
-> MongoDB persistence
```

The browser stores only an anonymous `client_id` and the guided-tour completion flag. Chat data is stored in MongoDB.

## 10. MongoDB collections

| Collection | Purpose |
|---|---|
| `conversations` | Thread title, owner client ID, preview, and timestamps |
| `messages` | User and assistant messages with active-version state |
| `response_versions` | Regenerated answer alternatives and source metadata |
| `feedback` | Version-specific rating, reason, and optional comment |

Indexes support conversation lookup, ordered messages, version history, and one feedback record per browser client and response version.

## 11. Frontend features

- Welcome screen and suggested questions
- Word-by-word SSE streaming
- Stop generation with `AbortController`
- Markdown answers
- Clickable inline citations and hover previews
- Expandable source metadata and snippets
- MongoDB chat history and resume after refresh
- Conversation deletion
- Answer regeneration and version history
- Version-specific thumbs-up/down feedback
- Required negative-feedback reason and optional comment
- First-time guided tour and replay button
- Responsive professional cybersecurity design

## 12. Development checks

```powershell
# Backend syntax
uv run python -m py_compile api.py chat_repository.py chat_models.py mongo_database.py mongo_schema.py

# Frontend quality
cd frontend
npm run lint
npm run build
```

## 13. Common issues

### Backend starts slowly

The embedding model, reranker, and local Qwen model are CPU-intensive. The first request after startup is usually the slowest.

### Health is degraded

Confirm Docker and Ollama are running:

```powershell
docker compose ps
ollama list
```

### No relevant answers

Rebuild the Weaviate collection:

```powershell
uv run python vector_store.py
```

### MongoDB authentication error

Confirm the username and password in `.env` match the credentials used when the MongoDB Docker volume was first created. For a fresh local database, remove and recreate the volume only when data loss is acceptable.

## 14. Project structure

```text
rag_setup/
|-- api.py                     # FastAPI and SSE endpoints
|-- clean_pdf.py               # Cached high-resolution PDF parsing
|-- chunking.py                # Control-aware chunking and metadata
|-- embedding.py               # Local BGE embedding model
|-- vector_store.py            # Weaviate schema and ingestion
|-- retrieval.py               # Hybrid retrieval and reranking
|-- generation.py              # Grounded Qwen generation and refusal
|-- mongo_database.py          # Async MongoDB lifecycle
|-- mongo_schema.py            # Collections and indexes
|-- chat_models.py             # API persistence models
|-- chat_repository.py         # Conversation/version/feedback persistence
|-- docker-compose.yml         # Weaviate and MongoDB
|-- data/                      # CIS Controls v8 PDF
|-- frontend/                  # React + TypeScript application
|-- pyproject.toml
`-- uv.lock
```

## 15. Privacy and grounding decision

The architecture is fully local to keep the document and questions private and avoid recurring cloud-AI API costs. The trade-off is slower inference on CPU. The assistant must use retrieved CIS evidence and must refuse unsupported questions with:

`The retrieved documents do not contain enough information to answer this question.`
