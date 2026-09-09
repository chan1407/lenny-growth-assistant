from dataclasses import dataclass
from typing import Any

from providers import (
    GenerationResult,
    MissingCredentialsError,
    ProviderUnavailableError,
    build_provider,
)
from settings import settings


class UnsupportedProviderError(RuntimeError):
    """Raised when LLM_PROVIDER names an unknown provider."""


@dataclass(frozen=True)
class AgentResponse:
    answer: str
    sources: list[dict[str, Any]]
    provider: str
    model: str


def _history_text(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return ""
    lines = ["CONVERSATION HISTORY:"]
    for message in history:
        lines.append(f"{message.get('role', 'user').upper()}: {message.get('content', '')}")
    return "\n".join(lines)


def _build_grounded_prompt(
    question: str,
    context: str,
    history: list[dict[str, Any]] | None,
) -> str:
    return f"""
You are The Lenny Growth Assistant.

Answer the user's product and growth question using ONLY the provided Lenny
Podcast transcript context. Conversation history is included only to resolve
references; it is not an additional factual source.

STRICT RULES:
- Do not use outside knowledge or tools.
- Do not invent facts, examples, companies, or recommendations.
- Every important claim must be supported by the transcript context.
- Mention the relevant guest/source when giving an insight.
- If the context does not contain enough information, clearly say:
  "The available Lenny transcripts don't provide enough information to answer this."
- Give a concise, useful answer.

{_history_text(history)}

TRANSCRIPT CONTEXT:
{context}

USER QUESTION:
{question}
"""


def generate_answer(
    question: str,
    context: str,
    sources: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> AgentResponse:
    prompt = _build_grounded_prompt(question, context, history)
    provider_name = settings.llm_provider

    try:
        provider = build_provider(provider_name)
    except ValueError as exc:
        raise UnsupportedProviderError(str(exc)) from exc

    try:
        result: GenerationResult = provider.generate(prompt)
    except (ProviderUnavailableError, MissingCredentialsError):
        fallback_name = settings.llm_fallback_provider
        if not fallback_name or fallback_name == provider_name:
            raise
        try:
            fallback = build_provider(fallback_name)
        except ValueError as exc:
            raise UnsupportedProviderError(str(exc)) from exc
        result = fallback.generate(prompt)

    return AgentResponse(
        answer=result.answer,
        sources=sources,
        provider=result.provider,
        model=result.model,
    )