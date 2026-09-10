from dataclasses import dataclass
from html import escape
import re
from typing import Any, Literal

from .providers import GenerationResult, MissingCredentialsError, ProviderUnavailableError, build_provider
from .settings import settings


ArtifactFormat = Literal["markdown", "html"]
SUPPORTED_ARTIFACT_FORMATS = {"markdown", "html"}
INSUFFICIENT_CONTEXT = "The available Lenny transcripts don't provide enough information to answer this."
GROUNDING_TERMS = {
    "activation",
    "acquisition",
    "experiment",
    "founder",
    "growth",
    "guest",
    "insight",
    "lenny",
    "onboarding",
    "product",
    "retention",
    "startup",
    "transcript",
    "user",
}


class UnsupportedArtifactFormatError(ValueError):
    """Raised when an artifact format is not supported."""


class UnsupportedArtifactProviderError(RuntimeError):
    """Raised when artifact generation cannot build the configured provider."""


@dataclass(frozen=True)
class ArtifactGeneration:
    content: str
    format: ArtifactFormat
    title: str
    provider: str
    model: str
    sources: list[dict[str, Any]]


def should_retrieve(prompt: str, history: list[dict[str, Any]] | None = None) -> bool:
    """Retrieve transcript context only when the request is plausibly factual."""
    text = prompt.lower()
    return any(term in text for term in GROUNDING_TERMS)


def _history_text(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return ""
    return "\n".join(
        f"{message.get('role', 'user').upper()}: {message.get('content', '')}"
        for message in history
    )


def build_artifact_prompt(
    prompt: str,
    artifact_format: ArtifactFormat,
    context: str,
    sources: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> str:
    source_metadata = "\n".join(
        f"- Guest: {source.get('guest')}; Episode: {source.get('title')}; "
        f"YouTube: {source.get('youtube_url')}; Published: {source.get('publish_date')}"
        for source in sources
    ) or "No transcript sources were retrieved."
    output_rules = (
        "Return readable Markdown with headings, short paragraphs, and lists where useful."
        if artifact_format == "markdown"
        else "Return a complete HTML document with inline CSS. Do not include JavaScript, forms, external resources, or event handlers."
    )

    return f"""
You are the Artifact Generation skill for Lenny Growth Assistant.

Create a useful {artifact_format} artifact from the user's instruction.
{output_rules}

GROUNDING RULES:
- Use only the supplied conversation and transcript context for Lenny-related facts.
- Do not invent guest claims, quotes, sources, metrics, or outside facts.
- Preserve relevant guest and episode attribution in the artifact.
- If the request requires Lenny facts but the supplied context is insufficient,
  return exactly: "{INSUFFICIENT_CONTEXT}"
- Do not mention these instructions in the artifact.

CONVERSATION HISTORY:
{_history_text(history)}

SOURCE METADATA:
{source_metadata}

RETRIEVED LENNY CONTEXT:
{context or "No transcript context was retrieved because this appears to be a formatting/presentation request."}

USER ARTIFACT REQUEST:
{prompt}
"""


def _looks_like_html_document(content: str) -> bool:
    lower = content.lower()
    return (
        "<!doctype html" in lower
        or "<html" in lower
        or "<style" in lower
        or "<body" in lower
    )


def _markdown_to_html_document(markdown: str, title: str) -> str:
    """Convert markdown provider output into a self-contained HTML artifact.

    This keeps the security model intact: inline CSS only, no external assets,
    no JavaScript, forms, or event handlers.
    """
    css = """
        :root { color-scheme: light; }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            background: #f8fafc;
            color: #1f2937;
            line-height: 1.55;
            padding: 24px;
        }
        main {
            max-width: 960px;
            margin: 0 auto;
            background: #ffffff;
            border: 1px solid #dbe3ea;
            border-radius: 12px;
            padding: 32px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
        }
        h1 { margin-top: 0; font-size: 2rem; color: #0f172a; }
        h2 { font-size: 1.35rem; color: #0f172a; margin: 1.0rem 0 0.4rem; }
        h3 { font-size: 1.1rem; color: #334155; margin: 0.9rem 0 0.35rem; }
        p { margin: 0.7rem 0; }
        ul { padding-left: 1.4rem; }
        li { margin: 0.4rem 0; }
        strong { color: #111827; }
        .artifact-date { color: #516174; font-size: 0.85rem; }
    """

    lines = [line.rstrip() for line in markdown.strip().splitlines()]
    html_lines = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "    <meta charset=\"utf-8\">",
        "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
        f"    <title>{escape(title)}</title>",
        "    <style>",
        css,
        "    </style>",
        "</head>",
        "<body>",
        "<main>",
        f"<h1>{escape(title)}</h1>",
    ]

    in_list = False
    for line in lines:
        if not line.strip():
            continue

        stripped = line.strip()
        if stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item = stripped[2:].strip()
            html_lines.append(f"<li>{_inline_markdown_to_html(item)}</li>")
            continue

        if in_list:
            html_lines.append("</ul>")
            in_list = False

        # Normalize visible markdown headings such as **Product Brief:**
        if stripped.startswith("**") and stripped.endswith(":*"):
            header = stripped.strip("*").strip(":")
            html_lines.append(f"<h2>{escape(header.strip())}</h2>")
            continue

        if stripped.startswith("**") and stripped.endswith("**"):
            header = stripped.strip("*").strip()
            html_lines.append(f"<h2>{escape(header)}</h2>")
            continue

        if re.match(r"^\*\*[^*]+:\*\*", stripped):
            # Preserve a heading-style line like **Title:** Streamlined ...
            # by turning the first bold token into a heading and the rest into paragraph text.
            match = re.match(r"^\*\*([^*]+):\*\*\s*(.*)$", stripped)
            if match:
                label = match.group(1)
                rest = match.group(2).strip()
                html_lines.append(f"<h2>{escape(label)}</h2>")
                if rest:
                    html_lines.append(f"<p>{_inline_markdown_to_html(rest)}</p>")
                continue

        if stripped.startswith("**") and ":" in stripped:
            label, rest = stripped[2:].split(":", 1)
            html_lines.append(f"<h2>{escape(label.strip())}</h2>")
            if rest.strip():
                html_lines.append(f"<p>{_inline_markdown_to_html(rest.strip())}</p>")
            continue

        # Single-line headers and bullet-free paragraphs
        html_lines.append(f"<p>{_inline_markdown_to_html(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")

    html_lines.extend(["</main>", "</body>", "</html>"])
    return "\n".join(html_lines)


def _inline_markdown_to_html(text: str) -> str:
    # Escape first so dangerous HTML remains inert and then selectively map only
    # the requested markdown-like emphasis patterns into safe HTML.
    safe_text = escape(text)
    safe_text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", safe_text)
    safe_text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", safe_text)
    return safe_text


def _title_from_prompt(prompt: str, artifact_format: ArtifactFormat) -> str:
    clean_prompt = " ".join(prompt.split())
    if not clean_prompt:
        return f"Generated {artifact_format} artifact"
    return clean_prompt[:80].rstrip(" .,!?-" )


def generate_artifact(
    prompt: str,
    artifact_format: str,
    context: str,
    sources: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> ArtifactGeneration:
    if artifact_format not in SUPPORTED_ARTIFACT_FORMATS:
        raise UnsupportedArtifactFormatError(
            f"Unsupported artifact format '{artifact_format}'. Use markdown or html."
        )

    normalized_format: ArtifactFormat = artifact_format  # type: ignore[assignment]
    if should_retrieve(prompt, history) and (not context.strip() or not sources):
        return ArtifactGeneration(
            content=INSUFFICIENT_CONTEXT,
            format=normalized_format,
            title="Insufficient transcript context",
            provider=settings.llm_provider,
            model=(settings.anthropic_model if settings.llm_provider == "anthropic" else settings.ollama_model),
            sources=[],
        )

    try:
        provider = build_provider(settings.llm_provider)
    except ValueError as exc:
        raise UnsupportedArtifactProviderError(str(exc)) from exc

    generation_prompt = build_artifact_prompt(
        prompt,
        normalized_format,
        context,
        sources,
        history,
    )
    try:
        result: GenerationResult = provider.generate(generation_prompt)
    except (ProviderUnavailableError, MissingCredentialsError):
        fallback_name = settings.llm_fallback_provider
        if not fallback_name or fallback_name == settings.llm_provider:
            raise
        try:
            provider = build_provider(fallback_name)
        except ValueError as exc:
            raise UnsupportedArtifactProviderError(str(exc)) from exc
        result = provider.generate(generation_prompt)

    content = result.answer
    if normalized_format == "html" and not _looks_like_html_document(content):
        content = _markdown_to_html_document(content, _title_from_prompt(prompt, normalized_format))

    return ArtifactGeneration(
        content=content,
        format=normalized_format,
        title=_title_from_prompt(prompt, normalized_format),
        provider=result.provider,
        model=result.model,
        sources=sources,
    )