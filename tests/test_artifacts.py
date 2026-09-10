import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import providers  # noqa: E402
from artifact import (  # noqa: E402
    INSUFFICIENT_CONTEXT,
    build_artifact_prompt,
    generate_artifact,
    should_retrieve,
)


def test_artifact_prompt_contains_grounding_and_format_instructions():
    prompt = build_artifact_prompt(
        "Create a retention brief from the Lenny insight",
        "markdown",
        "Guest: Guest A\nRetention improved after a fast value moment.",
        [{"guest": "Guest A", "title": "Episode A"}],
        [{"role": "user", "content": "What did we discuss?"}],
    )

    assert "Return readable Markdown" in prompt
    assert "Do not invent guest claims" in prompt
    assert "Guest A" in prompt
    assert "Retention improved" in prompt
    assert "What did we discuss?" in prompt


def test_markdown_artifact_generation_preserves_sources(monkeypatch):
    captured = {}

    class FakeProvider:
        def generate(self, prompt):
            captured["prompt"] = prompt
            return providers.GenerationResult("# Retention Brief", "ollama", "llama3.2:3b")

    monkeypatch.setattr("artifact.build_provider", lambda name: FakeProvider())
    sources = [{"guest": "Guest A", "title": "Episode A"}]

    result = generate_artifact(
        "Create a retention brief from the Lenny insight",
        "markdown",
        "Retention improved after a fast value moment.",
        sources,
    )

    assert result.format == "markdown"
    assert result.content == "# Retention Brief"
    assert result.sources == sources
    assert "Retention improved" in captured["prompt"]


def test_html_artifact_generation_requests_complete_safe_document(monkeypatch):
    captured = {}

    class FakeProvider:
        def generate(self, prompt):
            captured["prompt"] = prompt
            return providers.GenerationResult(
                "<!doctype html><html><head><style>body{font: sans-serif}</style></head><body><h1>Brief</h1></body></html>",
                "anthropic",
                "claude-sonnet-4-20250514",
            )

    monkeypatch.setattr("artifact.build_provider", lambda name: FakeProvider())

    result = generate_artifact(
        "Create a visual brief",
        "html",
        "",
        [],
    )

    assert result.format == "html"
    assert result.content.startswith("<!doctype html>")
    assert "complete HTML document" in captured["prompt"]
    assert "Do not include JavaScript" in captured["prompt"]
    assert result.provider == "anthropic"


def test_html_artifact_generation_converts_markdown_to_self_contained_html(monkeypatch):
    class FakeProvider:
        def generate(self, prompt):
            return providers.GenerationResult(
                "Here is a short product brief based on the conversation:\n\n"
                "**Product Brief:**\n\n"
                "**Title:** Streamlined Communication\n\n"
                "**Problem Statement:** We need to explain the problem clearly.",
                "ollama",
                "llama3.2:3b",
            )

    monkeypatch.setattr("artifact.build_provider", lambda name: FakeProvider())

    result = generate_artifact(
        "Create a short product brief from the current conversation.",
        "html",
        "Transcript context present for product brief generation.",
        [{"guest": "Guest A", "title": "Episode A"}],
    )

    assert result.format == "html"
    assert result.content.startswith("<!doctype html>")
    assert "<html" in result.content.lower()
    assert "<style" in result.content.lower()
    assert "<body" in result.content.lower()
    assert "**Product Brief:**" not in result.content
    assert "**Title:**" not in result.content
    assert "**Problem Statement:**" not in result.content


def test_lenny_request_requires_grounded_context(monkeypatch):
    monkeypatch.setattr(
        "artifact.build_provider",
        lambda name: pytest.fail("provider should not be built without grounded context"),
    )

    result = generate_artifact("Create a Lenny retention brief", "markdown", "", [])

    assert result.content == INSUFFICIENT_CONTEXT
    assert result.sources == []


def test_formatting_request_does_not_trigger_retrieval():
    assert should_retrieve("Turn this into a two-column HTML layout") is False
    assert should_retrieve("Create a product retention brief") is True


def test_unsupported_format_is_rejected():
    with pytest.raises(ValueError, match="markdown or html"):
        generate_artifact("Make something", "pdf", "", [])


def test_frontend_html_preview_is_sandboxed():
    app_source = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert 'sandbox=""' in app_source
    assert 'referrerPolicy="no-referrer"' in app_source
    assert 'allow-scripts' not in app_source