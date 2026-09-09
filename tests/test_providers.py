import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import agent  # noqa: E402
import providers  # noqa: E402


def test_ollama_provider_uses_configured_model_and_prompt(monkeypatch):
    calls = {}

    class FakeClient:
        def __init__(self, host, **kwargs):
            calls["host"] = host
            calls.update(kwargs)

        def chat(self, **kwargs):
            calls.update(kwargs)
            return {"message": {"content": "Grounded local answer"}}

    monkeypatch.setattr(providers.ollama, "Client", FakeClient)

    result = providers.OllamaProvider("llama3.2:3b", "http://ollama.test").generate("prompt")

    assert result.answer == "Grounded local answer"
    assert result.provider == "ollama"
    assert result.model == "llama3.2:3b"
    assert calls["host"] == "http://ollama.test"
    assert calls["timeout"] > 0
    assert calls["model"] == "llama3.2:3b"
    assert calls["messages"][0]["content"] == "prompt"


def test_anthropic_provider_uses_actual_agent_sdk_query(monkeypatch):
    import claude_agent_sdk

    captured = {}

    async def fake_query(*, prompt, options):
        captured["prompt"] = prompt
        captured["options"] = options
        yield claude_agent_sdk.AssistantMessage(
            content=[claude_agent_sdk.TextBlock(text="Cloud grounded answer")],
            model="claude-sonnet-4-20250514",
        )

    monkeypatch.setattr(claude_agent_sdk, "query", fake_query)

    result = providers.AnthropicProvider("claude-sonnet-4-20250514", "test-key").generate(
        "transcript context prompt"
    )

    assert result.answer == "Cloud grounded answer"
    assert result.provider == "anthropic"
    assert result.model == "claude-sonnet-4-20250514"
    assert captured["prompt"] == "transcript context prompt"
    assert captured["options"].model == "claude-sonnet-4-20250514"
    assert captured["options"].max_turns == 1
    assert captured["options"].tools == []


def test_anthropic_provider_requires_credentials():
    with pytest.raises(providers.MissingCredentialsError, match="ANTHROPIC_API_KEY"):
        providers.AnthropicProvider("claude-sonnet-4-20250514", None).generate("prompt")


def test_ollama_provider_unavailable_is_normalized(monkeypatch):
    class FailingClient:
        def __init__(self, host, **kwargs):
            pass

        def chat(self, **kwargs):
            raise TimeoutError("ollama timed out")

    monkeypatch.setattr(providers.ollama, "Client", FailingClient)

    with pytest.raises(providers.ProviderUnavailableError, match="Ollama is unavailable"):
        providers.OllamaProvider("llama3.2:3b", "http://ollama.test").generate("prompt")


def test_agent_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setattr(agent.settings, "llm_provider", "no-such-provider")

    with pytest.raises(agent.UnsupportedProviderError, match="no-such-provider"):
        agent.generate_answer("question", "context", [])


def test_agent_passes_rag_context_and_history_to_provider(monkeypatch):
    captured = {}

    class FakeProvider:
        def generate(self, prompt):
            captured["prompt"] = prompt
            return providers.GenerationResult("answer", "ollama", "llama3.2:3b")

    monkeypatch.setattr(agent.settings, "llm_provider", "ollama")
    monkeypatch.setattr(agent, "build_provider", lambda name: FakeProvider())

    result = agent.generate_answer(
        "What improves activation?",
        "Guest: Example Guest\nTranscript: Activation improves when users reach value quickly.",
        [{"guest": "Example Guest"}],
        [{"role": "user", "content": "What is onboarding?"}],
    )

    assert result.answer == "answer"
    assert "Activation improves when users reach value quickly." in captured["prompt"]
    assert "What is onboarding?" in captured["prompt"]
    assert "Do not use outside knowledge" in captured["prompt"]