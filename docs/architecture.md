# Architecture

## Request flow

The React frontend calls FastAPI. The API validates Pydantic models, loads
optional session history, retrieves transcript context when the action needs
facts, and sends a grounded prompt to the selected provider.

## Session and persistence flow

`POST /sessions` creates a PostgreSQL session. Chat, Ship 30, and artifact
operations load ordered messages by session ID. Chat and skills persist turns;
artifacts are stored in a separate `artifacts` table linked by foreign key.

## RAG flow

`backend/retriever.py` loads the checked-in processed transcript chunks,
embeddings, and SentenceTransformer model. It ranks chunks by normalized dot
product and returns source metadata. This algorithm is unchanged by deployment
work.

## Agent and providers

`backend/agent.py` orchestrates general answers. `backend/providers.py`
normalizes Ollama and Anthropic failures. Anthropic generation uses
`claude-agent-sdk` `query()` and `ClaudeAgentOptions` with tools disabled and a
single turn. Ollama remains the default local provider.

## Skills and artifacts

`backend/skills/ship30.py` owns essay instructions and metadata. `backend/artifact.py`
owns Markdown/HTML artifact instructions, conditional retrieval, and format
validation. Both reuse the provider layer and preserve source metadata.

## HTML isolation

The frontend never injects generated HTML into the app DOM. It uses a sandboxed
iframe with no permissions and no referrer. The empty sandbox means no scripts,
forms, same-origin access, popups, or top navigation. Source content is shown
only in a text `<pre>` disclosure.
