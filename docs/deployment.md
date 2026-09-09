# Deployment

## Local

The reliable local path is PostgreSQL + host Ollama + FastAPI + Vite. Copy
`.env.example` to `.env`, pull `llama3.2:3b`, start PostgreSQL, then run the
backend and frontend commands in the README.

## Docker Compose

`docker compose up --build` starts PostgreSQL, backend, and frontend. PostgreSQL
uses the named `postgres_data` volume. Backend startup waits for PostgreSQL to
be healthy. The frontend waits for the backend liveness check.

Ollama is intentionally not a Compose service by default. Running the model
inside Docker is unreliable and resource-heavy on Windows. Compose therefore
routes the backend to `host.docker.internal:11434`; Ollama must be installed,
started, and have the configured model pulled on the host.

## Environment and secrets

Use environment injection for `DATABASE_URL`, `ANTHROPIC_API_KEY`, provider
selection, model names, and timeout values. Never commit real secrets. The API
never includes keys in health responses or logs.

## Health and operations

- `/health/live` is a fast process liveness check.
- `/health/ready` checks PostgreSQL and the active provider with bounded client
  timeouts and returns 503 when dependencies are unavailable.
- Request logs include method, path, status, latency, provider operations, model,
  retrieval count, and safe error types, but not prompts or credentials.

## Cloud adaptation

For production, use managed PostgreSQL, a secret manager, TLS and authenticated
access, restricted CORS, centralized structured logs, metrics/tracing, backup
policies, rate limits, and a deliberate model-serving strategy. Host Ollama
routing is for local Docker Desktop only. Cloud deployment requires either
managed Ollama capacity or explicit Anthropic/provider configuration.
