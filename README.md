# Lenny Growth Assistant

## What it is

Lenny Growth Assistant is a grounded product and growth research workspace. It
answers questions from a local corpus of Lenny Podcast transcripts, remembers
conversation sessions, turns insights into Ship 30 for 30 essays, and creates
Markdown or HTML artifacts beside the chat.

## Problem and success metric

Product teams often have useful interview and podcast knowledge but no fast,
traceable way to turn it into an actionable answer or working draft. The
assessment success metric is a useful answer grounded in the transcript corpus,
with source metadata preserved and a reliable local demo path.

## Architecture

```text
React/Vite frontend
        |
        v
FastAPI API and session orchestration
        |
        +--> agent/provider layer --> Ollama or Claude Agent SDK
        |
        +--> RAG retriever --> transcript chunks + embeddings
        |
        +--> PostgreSQL --> sessions, messages, artifacts
```

`backend/providers.py` contains the Ollama and Anthropic providers. The
Anthropic path uses the official `claude-agent-sdk` package and its
`query()`/`ClaudeAgentOptions` API; it is not a handwritten HTTP client.
`backend/agent.py`, `backend/skills/`, and `backend/artifact.py` keep general
answers, Ship 30 writing, and artifacts separate from retrieval.

## Features

- Grounded Lenny Q&A with source metadata
- PostgreSQL session memory and message persistence
- Reusable Ship 30 for 30 skill
- Markdown and HTML artifact generation
- Markdown rendering and isolated HTML preview
- Local Ollama demo provider
- Optional Anthropic cloud provider

## Prerequisites

For the simplest local path:

- Python 3.12+
- Node.js 22+
- PostgreSQL 14+ running locally
- Ollama installed locally with `llama3.2:3b` pulled

Docker Compose can provide PostgreSQL, backend, and frontend. Ollama remains a
host dependency by default, which is the reliable choice on Windows.

## Assessment Deliverables / Documentation

The repository keeps the required assessment documents in the docs folder and
links them from this README so the demo and local setup stay GitHub-friendly.

- [docs/design.md](docs/design.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/manual-test-plan.md](docs/manual-test-plan.md)
- [docs/artifact-generation.md](docs/artifact-generation.md)
- [docs/provider-architecture.md](docs/provider-architecture.md)
- [docs/deployment.md](docs/deployment.md)
- [docs/agent-transcripts/](docs/agent-transcripts/)

Demo video: https://youtu.be/mZl-KPqHeoY

## Quick Start

From repository root:

```powershell
cd lenny-growth-assistant
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

In another terminal:

```powershell
cd C:\lenny-growth-assistant\frontend
npm install
npm run dev
```

Frontend: <http://localhost:5173>

The backend API starts on port 8000 with the module path `backend.main:app`.
Ollama is the default local demo provider. Anthropic is optional and requires
an `ANTHROPIC_API_KEY` and `LLM_PROVIDER=anthropic` configuration.

### Docker Compose

```powershell
docker compose up --build
```

This starts PostgreSQL on `localhost:5432`, the API on `localhost:8000`, and
the frontend on `localhost:5173`. On Docker Desktop for Windows, the backend
uses `http://host.docker.internal:11434` for host Ollama. Start Ollama on the
host before using chat generation.

## Ollama Setup

Install Ollama from [ollama.com](https://ollama.com), then run:

```powershell
ollama pull llama3.2:3b
ollama run llama3.2:3b
```

Verify the service with `ollama list` and check `GET /health`. Ollama is the
default local/demo provider, and Anthropic is optional. The API uses a
bounded `OLLAMA_TIMEOUT_SECONDS` so an unavailable service does not hang health
or generation indefinitely.

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string.
- `OLLAMA_BASE_URL`: Ollama URL; local default is `http://127.0.0.1:11434`.
- `OLLAMA_MODEL`: local model; default `llama3.2:3b`.
- `OLLAMA_TIMEOUT_SECONDS`: Ollama generation timeout, default `120`.
- `OLLAMA_HEALTH_TIMEOUT_SECONDS`: bounded Ollama health-probe timeout, default `3`.
- `DATABASE_CONNECT_TIMEOUT_SECONDS`: PostgreSQL connect timeout, default `5`.
- `LLM_PROVIDER`: `ollama` or `anthropic`; default `ollama`.
- `LLM_FALLBACK_PROVIDER`: optional explicit fallback provider.
- `ANTHROPIC_API_KEY`: local secret, never commit it.
- `ANTHROPIC_MODEL`: Claude model used by the Agent SDK.

## Provider Selection

Ollama is the default local/demo provider and requires no cloud credential.
It is the default provider in the shipped configuration and remains the safe
local demo path for fresh evaluators.

Anthropic is an optional cloud provider. To use it, install the project
requirements and configure an `ANTHROPIC_API_KEY` in the local environment
file, then set `LLM_PROVIDER=anthropic`. The implementation uses the
official `claude-agent-sdk` package from `backend/requirements.txt` and the
`ClaudeAgentOptions`/`query()` code path in `backend/providers.py`.

Fallback behavior is explicit and deterministic:

- If `LLM_FALLBACK_PROVIDER` is empty or not different from the selected
  provider, the route raises a structured provider error instead of silently
  switching providers.
- If `LLM_FALLBACK_PROVIDER` is set to a valid alternate provider name,
  the route catches the provider failure and tries the fallback provider only
  once. This match is visible in the route/failure logic in
  `backend/providers.py` and `backend/agent.py`.

Provider/model metadata is visible in `/health` and generation responses; keys
are never returned or logged.

## Data and RAG

Transcript source files live under `data/transcripts/episodes`. Ingestion
parses YAML frontmatter, cleans text, and creates overlapping chunks in
`data/processed_chunks.json`. `backend/embeddings.py` creates
`data/embeddings.npy` with `all-MiniLM-L6-v2`. The retriever ranks chunks by
normalized embedding dot product and returns guest, episode, YouTube, and date
metadata.

After changing transcripts, run the ingestion and embedding scripts from the
`backend` directory, then restart the API:

```powershell
python ingest.py
python embeddings.py
```

The checked-in processed data is preserved for the demo.

## API

- `GET /health`: application/provider status without secrets.
- `GET /health/live`: fast liveness response.
- `GET /health/ready`: bounded readiness check for PostgreSQL and the active provider.
- `POST /sessions`: create a session.
- `GET /sessions/{id}`: read session history.
- `POST /chat`: grounded conversational answer.
- `GET /search`: transcript retrieval inspection.
- `POST /skills/ship30`: grounded Ship 30 for 30 essay.
- `POST /artifacts`: persisted Markdown or HTML artifact generation.

## Artifact Security

Generated HTML is untrusted. The frontend renders it only in an iframe with an
empty `sandbox` attribute and `referrerPolicy="no-referrer"`; it grants neither
scripts nor same-origin access. This prevents access to the parent DOM,
storage, authentication/session data, and parent-origin APIs. The generator is
also instructed to omit scripts, forms, event handlers, and external resources.

## Testing

Repository tests are stored in the `tests/` directory and exercise the
backend API, provider selection, artifact generation, and the Ship 30 skill
paths with provider/database mocks. Live Ollama and PostgreSQL checks are
manual/integration checks, not required for the unit suite.

## Troubleshooting

- **Ollama unavailable:** start Ollama, verify `ollama list`, check `OLLAMA_BASE_URL`, and inspect `/health`.
- **Model missing:** run `ollama pull llama3.2:3b` or set `OLLAMA_MODEL` to an installed model.
- **Database unavailable:** start PostgreSQL, verify `DATABASE_URL`, and inspect `/health/ready`.
- **Port conflict:** change the host side of Compose mappings or run Vite/Uvicorn on another port.
- **Frontend cannot connect:** confirm the API is on port 8000 and the browser origin is allowed by CORS.
- **Anthropic failure:** set `LLM_PROVIDER=anthropic` and a real local `ANTHROPIC_API_KEY`; never put it in `.env.example`.

## Deployment

The Compose setup is suitable for a local assessment/demo and includes a
persistent PostgreSQL volume and health-gated services. A cloud deployment
would need managed PostgreSQL, secret management, TLS, authentication,
restricted CORS, an object store or database strategy for larger artifacts,
centralized logs, and a provider/embedding model strategy. Ollama on a cloud
host requires dedicated model-serving capacity or should be replaced by an
explicitly configured cloud provider; do not pretend host Ollama is available
inside a generic cloud container.

No Docker or cloud deployment was claimed as tested unless Docker is available
in the execution environment.
