from dataclasses import dataclass
from typing import Any

from .providers import (
    GenerationResult,
    MissingCredentialsError,
    ProviderUnavailableError,
    build_provider,
)
from .settings import settings


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
    history_text = _history_text(history)
    return f"""Read the transcript and answer the question.

{history_text}

TRANSCRIPT:
{context}

QUESTION:
{question}

Find the answer directly in the transcript.
Do not say the answer is missing if the transcript contains it.
Do not use outside knowledge.

ANSWER:
"""

def generate_answer(
    question: str,
    context: str,
    sources: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> AgentResponse:
    print("\n=== DEBUG QUESTION ===")
    print(question)
    print("\n=== DEBUG HISTORY ===")
    print(history)
    print("\n=== DEBUG CONTEXT ===")
    print(context[:5000])
    prompt = _build_grounded_prompt(question, context, history)
    provider_name = settings.llm_provider

    try:
        provider = build_provider(provider_name)
    except ValueError as exc:
        raise UnsupportedProviderError(str(exc)) from exc

    try:
        print("\n=== ACTUAL PROMPT SENT TO OLLAMA ===")
        print(prompt)
        print("=== END PROMPT ===\n")
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