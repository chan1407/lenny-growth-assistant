# Lenny Growth Assistant — PRD

## 1. User

The intended user is a product manager, growth practitioner, founder, or product team member who wants to quickly turn Lenny Podcast insights into grounded product decisions, written guidance, and reusable drafts.

## 2. Problem

Useful product and growth knowledge is distributed across a large transcript corpus. Users need a faster way to ask focused questions, preserve conversation context, identify supporting sources, and turn relevant insights into practical written artifacts without relying on unsupported model knowledge.

## 3. Goal

Enable users to explore Lenny Podcast knowledge through grounded conversational Q&A, continue conversations with session memory, create a Ship 30 for 30-style essay, and generate Markdown or HTML artifacts that can be reviewed beside the chat.

## 4. Success Metric

The primary proposed prototype metric is **grounded task completion rate**: the percentage of representative evaluation prompts that produce a useful answer or artifact supported by retrieved transcript sources and without fabricated claims. A target for the take-home prototype is at least 80% on a curated evaluation set.

Supporting proposed metrics:

- Source attribution coverage: at least 90% of factual evaluation answers include relevant source metadata.
- Empty-context safety: 100% of insufficient-retrieval evaluation cases return the defined fallback rather than an invented answer.
- Session continuity: at least 95% of multi-turn evaluation cases include the expected prior session context.
- Reliability: successful API responses for valid mocked-provider test cases, with dependency failures returning structured errors.

These are proposed evaluation targets, not measured production results. The current measured results are the passing automated test suite, successful frontend build, valid Compose configuration, and verified local Ollama generation.

## 5. Assumptions

- The Lenny transcript corpus is available locally under `data/transcripts/episodes` and has been processed into chunks and embeddings.
- Transcript metadata such as guest, episode title, YouTube URL, and publication date is available for source display.
- Local Ollama is the default demo provider and may be unavailable on another machine until installed and configured.
- The configured local model is `llama3.2:3b`, but the model name can be changed through environment configuration.
- Anthropic is an optional cloud provider and requires a valid local API key when selected.
- PostgreSQL is used for session, message, and artifact persistence and must be reachable for those workflows.
- The checked-in transcript corpus is not automatically refreshed and may become stale.
- Lenny-related factual answers and generated content must remain grounded in retrieved transcript context; the providers are not treated as unrestricted factual search engines.

## 6. Scope

### In scope

- Grounded conversational product and growth Q&A.
- PostgreSQL-backed session and conversation persistence.
- Transcript RAG using processed chunks, embeddings, and similarity retrieval.
- Configurable provider abstraction.
- Local Ollama provider for the demo.
- Optional Anthropic provider through the Claude Agent SDK.
- Provider and model visibility in API responses and the UI.
- Reusable Ship 30 for 30 content skill.
- Markdown and HTML artifact generation.
- Markdown artifact rendering in the frontend.
- Isolated HTML artifact preview in a sandboxed iframe.
- Guest, episode, video, and publication source metadata preservation.
- Health, readiness, timeout, logging, Docker Compose, and structured failure behavior.

### Out of scope

- Artifact editing, version history, collaboration, or export workflows.
- User authentication, authorization, billing, or multi-tenant isolation.
- Full production-grade Markdown parsing and sanitization features.
- Interactive JavaScript execution inside generated HTML artifacts.
- Web search, live transcript discovery, or unrestricted external knowledge retrieval.
- Automatic transcript refresh scheduling and corpus administration UI.
- Ship 30 content analytics or publishing integrations.
- Docker deployment to a cloud provider, managed model serving, or production networking.
- Production rate limiting, quotas, audit trails, and enterprise compliance controls.

## 7. User Experience

1. The user starts a session from the web application.
2. The user asks a Lenny, product, or growth question.
3. The system retrieves relevant transcript chunks and returns a grounded answer with source information.
4. The user continues the conversation; prior messages are loaded from PostgreSQL and supplied as conversational context.
5. The user requests a Ship 30 for 30 essay from the current question or conversation.
6. The user requests a Markdown or HTML artifact, selecting the desired format.
7. The generated artifact appears beside the chat. Markdown is rendered as readable content; HTML is previewed in an isolated sandboxed iframe, with source content available for inspection.

## 8. Product Decisions / Trade-offs

- **Local Ollama for the demo:** Local inference supports privacy, predictable setup after model installation, and a working offline-oriented demonstration. The trade-off is local hardware and model availability.
- **Optional Anthropic provider:** Cloud generation provides an alternative when local resources are insufficient, but introduces credential, cost, network, and availability dependencies.
- **Transcript RAG instead of unrestricted web knowledge:** Retrieval makes Lenny-related claims traceable and limits unsupported facts. The trade-off is that answers are limited by corpus coverage and retrieval quality.
- **PostgreSQL persistence:** Sessions, messages, and artifacts survive process restarts and can be queried consistently. The trade-off is an additional local dependency.
- **Sandboxed iframe for generated HTML:** Untrusted HTML is isolated from the application DOM, storage, and parent-origin APIs. The trade-off is that scripts, same-origin behavior, forms, and interactive external content are intentionally unavailable.
- **Separate artifact skill/module:** Artifact formatting and grounding rules can evolve independently from normal chat and Ship 30. The trade-off is an additional generation path to test and maintain.
- **Configurable provider/model:** The same API and UI can expose the active provider and model while allowing local or cloud operation. The trade-off is more configuration and failure modes.

## 9. Risks and Mitigations

- **Hallucination or weak grounding:** Use transcript retrieval, explicit grounded prompts, source metadata, insufficient-context fallbacks, and evaluation cases that check attribution.
- **Stale transcript corpus:** Document corpus provenance and refresh/re-ingestion commands; future work should automate freshness checks.
- **Ollama unavailable:** Use bounded timeouts, health/readiness endpoints, structured provider errors, and an explicitly configured optional fallback.
- **Model latency:** Configure separate generation and health timeouts, expose provider/model information, and report failures without hanging requests indefinitely.
- **Database failure:** Use bounded PostgreSQL connection attempts, structured 503 responses, persistence tests, and readiness reporting.
- **Untrusted generated HTML:** Render only inside an iframe with an empty sandbox, no scripts, no same-origin permission, and no referrer; do not inject HTML into the main DOM.
- **Cloud credential failure:** Validate credentials at provider use time, return a safe structured error, never expose keys, and keep cloud use opt-in.

## 10. Future Improvements

- Improve retrieval with reranking, query expansion, and relevance thresholds.
- Automate transcript refresh, ingestion, embedding generation, and corpus validation.
- Add richer inline citations and source excerpts in answers and artifacts.
- Add production authentication, authorization, and tenant isolation.
- Add centralized metrics, tracing, alerting, and structured log aggregation.
- Adapt the Compose setup for a managed cloud deployment.
- Build a curated evaluation dataset for grounding, retrieval, artifact quality, and regression testing.

## 11. Prototype vs Production

### Prototype implemented for the assessment

The prototype includes grounded transcript Q&A, session and message persistence,
Ollama and optional Claude Agent SDK providers, provider visibility, Ship 30 and
artifact skills, Markdown rendering, sandboxed HTML previews, health endpoints,
resilience handling, Docker Compose configuration, and automated backend/frontend
validation.

### Additional production requirements

Production would require authenticated access, managed PostgreSQL with backups,
secret management, restricted CORS and TLS, rate limiting, stronger input and
output controls, centralized observability, operational alerting, automated
corpus refresh, a maintained evaluation set, deployment-specific model serving,
and a documented data retention and privacy policy.
