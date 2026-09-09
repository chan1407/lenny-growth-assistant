from dataclasses import dataclass
import logging

import anyio
import ollama

from settings import settings


logger = logging.getLogger("lenny_growth_assistant.providers")
SUPPORTED_PROVIDERS = {"ollama", "anthropic"}


class ProviderError(RuntimeError):
    """Base error for a configured LLM provider."""


class ProviderUnavailableError(ProviderError):
    """Raised when a provider cannot complete a request."""


class MissingCredentialsError(ProviderError):
    """Raised when a cloud provider has no credentials configured."""


@dataclass(frozen=True)
class GenerationResult:
    answer: str
    provider: str
    model: str


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str) -> GenerationResult:
        try:
            response = ollama.Client(host=self.base_url, timeout=settings.ollama_timeout_seconds).chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response["message"]["content"]
        except Exception as exc:
            logger.warning(
                "provider_failure provider=ollama model=%s error_type=%s",
                self.model,
                type(exc).__name__,
            )
            raise ProviderUnavailableError(
                f"Ollama is unavailable or timed out at '{self.base_url}'."
            ) from exc

        return GenerationResult(answer=answer, provider=self.name, model=self.model)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None) -> None:
        self.model = model
        self.api_key = api_key

    def generate(self, prompt: str) -> GenerationResult:
        if not self.api_key:
            raise MissingCredentialsError(
                "Anthropic is selected but ANTHROPIC_API_KEY is not configured."
            )

        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                TextBlock,
                query,
            )
        except ImportError as exc:  # pragma: no cover - dependency packaging guard
            raise ProviderUnavailableError(
                "The Claude Agent SDK is not installed. Install claude-agent-sdk."
            ) from exc

        async def run_query() -> str:
            text_parts: list[str] = []
            options = ClaudeAgentOptions(
                model=self.model,
                max_turns=1,
                tools=[],
                permission_mode="dontAsk",
                env={"ANTHROPIC_API_KEY": self.api_key or ""},
            )
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    text_parts.extend(
                        block.text for block in message.content if isinstance(block, TextBlock)
                    )
            return "".join(text_parts).strip()

        try:
            answer = anyio.run(run_query)
        except Exception as exc:
            logger.warning(
                "provider_failure provider=anthropic model=%s error_type=%s",
                self.model,
                type(exc).__name__,
            )
            raise ProviderUnavailableError(
                "Anthropic Agent SDK could not complete the request."
            ) from exc

        if not answer:
            raise ProviderUnavailableError("Anthropic returned an empty response.")

        return GenerationResult(answer=answer, provider=self.name, model=self.model)


def build_provider(provider_name: str):
    if provider_name == "ollama":
        return OllamaProvider(settings.ollama_model, settings.ollama_base_url)
    if provider_name == "anthropic":
        return AnthropicProvider(settings.anthropic_model, settings.anthropic_api_key)
    raise ValueError(f"Unsupported LLM provider '{provider_name}'.")