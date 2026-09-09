# Manual Test Plan

## Prerequisites

Start PostgreSQL and the backend, then start the frontend. For the default local
path, start Ollama and ensure `llama3.2:3b` is installed. Confirm `/health`
reports the intended provider and model. Use a disposable session and do not
enter real credentials into screenshots or evidence.

## Cases

| ID    | Scenario             | Steps                                                                                                 | Expected result                                                                                                                                                            |
| ----- | -------------------- | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MT-01 | New session          | Open the frontend, wait for initialization, and inspect the session-backed chat.                      | A new session is created; the chat is usable and the active provider/model is visible.                                                                                     |
| MT-02 | Grounded question    | Ask a question answerable from the Lenny corpus, such as an onboarding or retention question.         | The answer is concise, grounded in retrieved transcript context, and includes relevant source metadata.                                                                    |
| MT-03 | Follow-up question   | Ask a grounded question, then ask a follow-up referring to the prior answer in the same session.      | The second answer uses the prior session messages and remains grounded; the session history persists.                                                                      |
| MT-04 | Unsupported question | Ask a question requiring facts absent from the available transcripts.                                 | The defined insufficient-context sentence is returned rather than an invented answer.                                                                                      |
| MT-05 | Ship 30              | Ask a grounded product/growth question and select `Ship 30 essay`.                                    | A separate `ship30_for_30` essay is returned with the required narrative structure, practical takeaway, skill version, and sources.                                        |
| MT-06 | Markdown artifact    | In an active session, request a Markdown brief and select `Markdown`.                                 | The artifact is persisted and displayed with readable headings, paragraphs/lists, source metadata, provider, and model.                                                    |
| MT-07 | HTML artifact        | In an active session, request an HTML brief and select `HTML preview`.                                | A complete HTML preview appears in the viewer; `View source` exposes the returned content. Scripts, forms, event handlers, and external resources are not expected to run. |
| MT-08 | Source metadata      | Inspect the response/viewer for a grounded answer, Ship 30 essay, and artifact.                       | Guest, episode title, YouTube URL, and publication date are preserved where present; no API key is displayed.                                                              |
| MT-09 | Ollama unavailable   | Stop Ollama or point `OLLAMA_BASE_URL` at an unreachable local endpoint, then call chat or readiness. | The UI shows a bounded, structured provider-unavailable error; the request does not hang indefinitely. `/health/ready` reports not ready for the local provider.           |
| MT-10 | Invalid session      | Submit chat, Ship 30, or artifact generation with a nonexistent UUID session ID.                      | The API returns a structured 404 session-not-found response; no artifact or message is created. Malformed UUID input returns structured validation failure.                |
| MT-11 | Backend unavailable  | Stop the API while the frontend is open, then submit a message or artifact request.                   | The UI shows a connection/provider error without crashing; restart the API and confirm the frontend can recover on a new request.                                          |

## Evidence to capture

For each passing case, record the case ID, provider/model, and a redacted
screenshot or response summary. For MT-02 through MT-08, preserve the visible
source metadata. For MT-09 through MT-11, preserve the HTTP status and error
code. Never capture `ANTHROPIC_API_KEY`, database credentials, or session data
belonging to another user.

## Provider-specific repeat

To verify the real Anthropic route, set `LLM_PROVIDER=anthropic`, set a local
`ANTHROPIC_API_KEY`, and set `ANTHROPIC_MODEL` if needed. Repeat MT-02 and
confirm the response provider/model identify Anthropic. Remove the key after the
check and do not commit the `.env` file. Repeat the normal plan with
`LLM_PROVIDER=ollama` and `OLLAMA_MODEL=llama3.2:3b` to verify the local path.
