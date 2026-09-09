# Ship 30 for 30 Content Skill

**Name:** `ship30_for_30`

**Version:** `1.0`

This reusable skill turns retrieved, grounded Lenny transcript insights into a
Ship 30 for 30-style essay. It is separate from normal chat so the writing
format, source handling, and output contract can evolve without changing the
general-purpose assistant.

## Inputs

- The current user question.
- Relevant conversation history from the active session.
- Retrieved Lenny transcript text.
- Source metadata including guest, episode, YouTube URL, and publication date.

## Writing rules

- Start with a strong opening hook.
- Progress through a clear narrative: problem, insight, development, and action.
- Use skimmable headings, short paragraphs, bullets where useful, and bold emphasis where useful.
- Include a specific practical takeaway.
- Target approximately 1,250 words, with a practical range of 1,100-1,400 words.
- Avoid generic filler and unsupported claims.

## Grounding

The skill supplies transcript context and source metadata directly to the
configured provider. The prompt prohibits outside knowledge and invented guest
claims. When retrieval returns no usable sources, the skill returns the existing
insufficient-context sentence without invoking a provider.

The API endpoint is `POST /skills/ship30`. It accepts the same `message` and
optional `session_id` shape as chat and returns the essay, skill name/version,
provider, model, and source metadata.
