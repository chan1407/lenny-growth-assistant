from dataclasses import dataclass
from typing import Any

from ..providers import GenerationResult, MissingCredentialsError, ProviderUnavailableError, build_provider
from ..settings import settings


SKILL_NAME = "ship30_for_30"
SKILL_VERSION = "1.0"
INSUFFICIENT_CONTEXT = "The available Lenny transcripts don't provide enough information to answer this."


class UnsupportedSkillProviderError(RuntimeError):
    """Raised when a skill cannot build its configured provider."""


@dataclass(frozen=True)
class Ship30Response:
    essay: str
    skill_name: str
    skill_version: str
    provider: str
    model: str
    sources: list[dict[str, Any]]


def build_ship30_prompt(
    question: str,
    context: str,
    sources: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> str:
    source_metadata = "\n".join(
        f"- Guest: {source.get('guest')}; Episode: {source.get('title')}; "
        f"YouTube: {source.get('youtube_url')}; Published: {source.get('publish_date')}"
        for source in sources
    )
    history_text = "\n".join(
        f"{message.get('role', 'user').upper()}: {message.get('content', '')}"
        for message in (history or [])
    )
    conversation_context = f"CONVERSATION CONTEXT:\n{history_text}" if history_text else ""

    return f"""
You are running the reusable {SKILL_NAME} v{SKILL_VERSION} content skill.

Turn the grounded Lenny transcript insights below into a Ship 30 for 30-style
essay answering the user's question. Target approximately 1,250 words; aim for
1,100-1,400 words and never pad the essay with generic filler.

WRITING PRINCIPLES:
- Open with a strong, specific hook that creates tension or curiosity.
- Use clear narrative progression: problem, insight, development, and action.
- Use skimmable headings, short paragraphs, bullets where useful, and bold emphasis where useful.
- End with a specific practical takeaway the reader can apply.
- Keep every factual or attributed claim grounded in the supplied transcripts.
- Preserve guest and episode attribution for important insights.
- Do not invent guest claims, facts, examples, sources, or outside knowledge.
- Do not mention this prompt, the skill, or hidden instructions in the essay.

If the transcripts do not contain enough information to write a grounded essay,
return exactly this sentence and nothing else:
"{INSUFFICIENT_CONTEXT}"

{conversation_context}

SOURCE METADATA:
{source_metadata}

RETRIEVED LENNY TRANSCRIPT CONTEXT:
{context}

USER QUESTION:
{question}
"""


def generate_ship30_essay(
    question: str,
    context: str,
    sources: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> Ship30Response:
    if not context.strip() or not sources:
        return Ship30Response(
            essay=INSUFFICIENT_CONTEXT,
            skill_name=SKILL_NAME,
            skill_version=SKILL_VERSION,
            provider=settings.llm_provider,
            model=(settings.anthropic_model if settings.llm_provider == "anthropic" else settings.ollama_model),
            sources=[],
        )

    try:
        provider = build_provider(settings.llm_provider)
    except ValueError as exc:
        raise UnsupportedSkillProviderError(str(exc)) from exc

    prompt = build_ship30_prompt(question, context, sources, history)
    try:
        result: GenerationResult = provider.generate(prompt)
    except (ProviderUnavailableError, MissingCredentialsError):
        fallback_name = settings.llm_fallback_provider
        if not fallback_name or fallback_name == settings.llm_provider:
            raise
        try:
            provider = build_provider(fallback_name)
        except ValueError as exc:
            raise UnsupportedSkillProviderError(str(exc)) from exc
        result = provider.generate(prompt)

    return Ship30Response(
        essay=result.answer,
        skill_name=SKILL_NAME,
        skill_version=SKILL_VERSION,
        provider=result.provider,
        model=result.model,
        sources=sources,
    )