import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import providers  # noqa: E402
from skills.ship30 import (  # noqa: E402
    INSUFFICIENT_CONTEXT,
    SKILL_NAME,
    SKILL_VERSION,
    build_ship30_prompt,
    generate_ship30_essay,
)


def test_ship30_prompt_contains_writing_principles_and_inputs():
    prompt = build_ship30_prompt(
        "How do teams improve retention?",
        "Guest: Guest A\nRetention improves after a fast value moment.",
        [{"guest": "Guest A", "title": "Episode A", "youtube_url": "https://example.com/a"}],
        [{"role": "user", "content": "What did we discuss?"}],
    )

    for phrase in (
        "strong, specific hook",
        "narrative progression",
        "skimmable headings",
        "short paragraphs",
        "bullets where useful",
        "bold emphasis",
        "specific practical takeaway",
        "1,100-1,400 words",
        "Do not invent guest claims",
        "Guest A",
        "Retention improves",
        "What did we discuss?",
    ):
        assert phrase in prompt


def test_ship30_passes_transcript_context_to_provider(monkeypatch):
    captured = {}

    class FakeProvider:
        def generate(self, prompt):
            captured["prompt"] = prompt
            return providers.GenerationResult("# Grounded essay", "ollama", "llama3.2:3b")

    monkeypatch.setattr("skills.ship30.build_provider", lambda name: FakeProvider())

    response = generate_ship30_essay(
        "How do teams improve retention?",
        "Transcript claim: retention improves after a fast value moment.",
        [{"guest": "Guest A", "title": "Episode A"}],
    )

    assert response.skill_name == SKILL_NAME
    assert response.skill_version == SKILL_VERSION
    assert "retention improves after a fast value moment" in captured["prompt"]
    assert "Guest A" in captured["prompt"]


def test_ship30_skill_returns_insufficient_context_without_provider(monkeypatch):
    monkeypatch.setattr(
        "skills.ship30.build_provider",
        lambda name: pytest.fail("provider should not be built without grounded sources"),
    )

    response = generate_ship30_essay("Question", "", [])

    assert response.essay == INSUFFICIENT_CONTEXT
    assert response.sources == []