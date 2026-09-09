# Design

The product is a local-first research assistant. Chat is the primary workflow;
Ship 30 and artifacts are explicit actions so their output contracts do not
change normal answers.

- **Grounding:** retrieval supplies transcript chunks and source metadata before generation.
- **Memory:** a session owns ordered user/assistant messages in PostgreSQL.
- **Skills:** Ship 30 and artifact generation are separate reusable modules.
- **Providers:** one normalized provider interface supports local Ollama and the official Claude Agent SDK.
- **Artifacts:** generated content is persisted and rendered beside chat.

The main trade-off is conservative failure behavior: missing context returns a
known fallback instead of a plausible but unsupported answer. The local demo
prioritizes Ollama; cloud provider fallback is opt-in.
