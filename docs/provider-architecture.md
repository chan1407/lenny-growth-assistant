# Provider Architecture

The backend separates transcript retrieval, agent orchestration, and LLM providers:

- `backend/retriever.py` retrieves and ranks Lenny transcript chunks.
- `backend/agent.py` builds the grounded prompt, supplies the user question, retrieved context, and conversation history to a provider, and returns the answer, sources, provider, and model.
- `backend/providers.py` contains the provider implementations and normalized provider errors.

## Providers

Ollama is the default local/demo provider. It uses `OLLAMA_MODEL` (default `llama3.2:3b`) and `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`). The local demo does not require a cloud credential.

Anthropic uses the official `claude-agent-sdk` Python package and its `query()` plus `ClaudeAgentOptions` API. The pinned project version is `0.2.152`; it requires `ANTHROPIC_API_KEY` and uses `ANTHROPIC_MODEL`.

Set `LLM_PROVIDER=ollama` or `LLM_PROVIDER=anthropic`. The active provider and model are returned by `/health` and `/chat`, and the frontend displays them. API keys are never returned by the API.

## Grounding and fallback

Every provider receives the retrieved transcript context in a prompt that forbids outside knowledge and tools for factual answers. The existing insufficient-context response remains in place when retrieval returns no results.

Provider fallback is disabled by default. To enable it explicitly, set `LLM_FALLBACK_PROVIDER` to another supported provider. If the selected provider is unavailable or missing credentials, the configured fallback is tried; otherwise the API returns a structured 503 provider error. A configured fallback does not change retrieval or allow the model to use unrelated sources.

## Configuration

Copy the placeholders from `.env.example` into the local `.env` and set only the provider you intend to run. Never commit a real `ANTHROPIC_API_KEY`.

## Ship 30 for 30 skill

The reusable `ship30_for_30` skill turns grounded Lenny transcript insights
into an approximately 1,250-word Ship 30 for 30-style essay. It is implemented
separately from normal `/chat` so its writing rules and response contract do
not become a one-off chat prompt or change ordinary answers.

`POST /skills/ship30` receives the current question, optional active session
history, retrieved transcript text, and source metadata. It returns the essay,
skill name/version, provider, model, and source metadata. The skill requires
retrieved sources, includes guest and episode information in its generation
prompt, forbids outside knowledge and invented claims, and returns the existing
insufficient-context sentence when retrieval has no usable material.
