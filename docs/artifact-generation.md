# Artifact Generation

`POST /artifacts` creates a persisted artifact from an existing PostgreSQL session.
The request contains a `session_id`, a user `prompt`, and `format` (`markdown` or
`html`). The response includes `artifact_id`, title, content, provider, model,
source metadata, and creation time.

## Flow

1. The API validates the session and loads its conversation history.
2. A small request classifier decides whether the prompt is likely asking for
   Lenny/product/growth facts. Only those requests use the existing transcript
   retriever. Presentation-only requests avoid unrelated retrieval.
3. The dedicated artifact module builds a format-specific, grounded generation
   prompt and calls the configured provider.
4. The generated content and source metadata are stored in PostgreSQL in the
   `artifacts` table.
5. The frontend displays Markdown as formatted content or HTML as an isolated
   preview beside the chat.

## Markdown and HTML

Markdown is rendered as readable headings, paragraphs, lists, and emphasis in
React. HTML artifacts are complete documents intended for preview. The source
content remains available behind `View source` for inspection.

## HTML security

Generated HTML is untrusted. The viewer uses an `<iframe srcDoc>` with an empty
`sandbox` attribute and `referrerPolicy="no-referrer"`. It does not grant
`allow-scripts`, `allow-same-origin`, forms, popups, or top-navigation access.
Because the frame has an opaque origin, it cannot access the parent DOM,
application storage, authentication/session data, or parent-origin APIs. The
artifact generator is also instructed to omit scripts, forms, event handlers,
and external resources. The viewer is a preview, not an execution environment;
interactive HTML and external assets are intentionally limited.

## Limitations

The request classifier is intentionally conservative and keyword-based. A
formatting request may not retrieve transcripts unless its prompt clearly
references Lenny/product/growth material. Artifact content is model-generated,
so source metadata is preserved for inspection but does not constitute a claim
that every generated sentence is correct.
