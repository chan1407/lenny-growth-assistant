from dataclasses import dataclass
from typing import Any, Literal

from providers import GenerationResult, MissingCredentialsError, ProviderUnavailableError, build_provider
from settings import settings


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

    return ArtifactGeneration(
        content=result.answer,
        format=normalized_format,
        title=_title_from_prompt(prompt, normalized_format),
        provider=result.provider,
        model=result.model,
        sources=sources,
    )