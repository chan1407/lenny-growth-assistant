# Assessment Readiness Pass: 2026-09-09

## Scope

This was a final, focused assessment-readiness pass for provider routing,
configuration, grounded retrieval, Ship 30, artifacts, HTML isolation, and
required validation. Docker, WSL, BIOS, and deployment infrastructure were not
changed or tested.

## Assessment summary: provider path

Source inspection and the provider test show that Anthropic is an active
production path, not unused code:

1. `backend/main.py` calls `generate_answer()` for `/chat`.
2. `backend/agent.py` builds the selected provider from `settings.llm_provider`.
3. `backend/providers.py` builds `ClaudeAgentOptions` and asynchronously iterates
   `claude_agent_sdk.query(prompt=prompt, options=options)` when Anthropic is
   selected.
4. The provider test monkeypatches the SDK `query` function and verifies the
   prompt, model, `max_turns=1`, and empty tools list.

Ollama remains the default local provider. `OLLAMA_MODEL` defaults to
`llama3.2:3b`, `OLLAMA_BASE_URL` defaults to `http://127.0.0.1:11434`, and the
provider test verifies that the configured model and prompt reach
`ollama.Client(...).chat(...)`.

Provider and model selection are environment-configurable through `LLM_PROVIDER`,
`LLM_FALLBACK_PROVIDER`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, and `ANTHROPIC_MODEL`.
Anthropic credentials are read from `ANTHROPIC_API_KEY` and are not returned or
logged by the application. The local `.env` contained no Anthropic value during
this pass; the example file contains placeholders only. This workspace did not
expose Git metadata or a root ignore file, so repository-level tracking of `.env`
could not be independently verified here.

## Assessment summary: grounding and source behavior

Chat retrieves three transcript chunks, passes transcript text and source
metadata into a grounded provider prompt, and returns guest, episode, YouTube,
and publication-date metadata in the response and persisted message metadata.
The defined insufficient-context sentence is returned when chat retrieval is
empty. Session history is supplied to follow-up generation.

The implementation matches the PRD's traceable RAG direction. A remaining
quality limitation is that the retriever always returns the top-ranked chunks
when the corpus is non-empty; there is no explicit similarity threshold. The
prompt and empty-retrieval fallback reduce risk, but retrieval quality and
unsupported-question behavior still need the manual checks in the test plan.

## Assessment summary: Ship 30

`ship30_for_30` v1.0 is separate from normal chat, receives transcript context,
conversation history, and source metadata, requests the required narrative
shape and approximately 1,250 words within the 1,100-1,400 target, forbids
invented claims, and requires a practical takeaway. It returns the skill name,
version, provider, model, essay, and sources. No-provider invocation occurs
when context or sources are absent.

## Assessment summary: artifacts and isolation

Markdown artifacts are generated, persisted, and rendered in the frontend.
HTML artifacts are shown using `iframe srcDoc` with `sandbox=""` and
`referrerPolicy="no-referrer"`; the frontend does not grant scripts or
same-origin access. The artifact prompt also prohibits scripts, forms, event
handlers, and external resources. The source is available through `View source`.

## Actual log excerpt: backend validation

Observed command (run from the project workspace):

```text
.\\backend\\.venv\\Scripts\\python.exe -m pytest -q
.................................                                        [100%]
33 passed, 1 warning in 112.75s (0:01:52)
```

The warning was a dependency deprecation warning from Starlette's test client;
it did not fail the suite.

## Actual log excerpt: failed attempt and correction

The first frontend command was issued from the parent terminal directory:

```text
npm error code ENOENT
npm error path F:\\lenny-growth-assistant\\package.json
npm error Could not read package.json
```

Correction: run the same build from `f:\lenny-growth-assistant\frontend`.
This was a command-location failure, not a frontend application failure.

## Actual log excerpt: frontend validation

Observed after correcting the working directory:

```text
> frontend@0.0.0 build
> vite build

vite v8.2.2 building client environment for production...
✓ 17 modules transformed.
✓ built in 11.40s
```

## Unverified live checks

No live Anthropic request was made because no credential was supplied. No live
Ollama generation or PostgreSQL-backed browser workflow was claimed by this
record. Use `docs/manual-test-plan.md` for the required manual checks.
