import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import main  # noqa: E402

client = TestClient(main.app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "ollama" in payload
    assert "database" in payload
    assert "llm" in payload
    assert isinstance(payload["ollama"]["configured"], bool)
    assert isinstance(payload["database"]["configured"], bool)


def test_live_health_is_fast_and_dependency_free():
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "application": "alive"}


def test_ready_health_reports_unavailable_database(monkeypatch):
    def fail_connection():
        raise main.DatabaseUnavailableError("database down")

    monkeypatch.setattr("db.get_connection", fail_connection)
    monkeypatch.setattr(main.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(main.settings, "anthropic_api_key", "")

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["database"]["reachable"] is False


def test_search_endpoint(monkeypatch):
    def fake_search(query: str, top_k: int = 5):
        return [
            {
                "score": 0.91,
                "text": "This is a sample transcript chunk about onboarding and retention.",
                "source": {
                    "guest": "Example Guest",
                    "title": "Example Episode",
                    "youtube_url": "https://example.com/video",
                    "publish_date": "2024-01-01",
                },
            }
        ]

    monkeypatch.setattr(main, "search", fake_search)

    response = client.get("/search", params={"q": "onboarding", "top_k": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "onboarding"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["source"]["guest"] == "Example Guest"


def test_chat_validation_requires_message():
    response = client.post("/chat", json={})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "validation_error"
    assert "detail" in payload


def test_create_session(monkeypatch):
    created = {
        "session_id": "11111111-1111-4111-8111-111111111111",
        "user_metadata": {"plan": "trial"},
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1),
        "messages": [],
    }

    monkeypatch.setattr(main, "create_session", lambda metadata=None: created)

    response = client.post("/sessions", json={"user_metadata": {"plan": "trial"}})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == created["session_id"]
    assert payload["user_metadata"]["plan"] == "trial"


def test_get_session(monkeypatch):
    session = {
        "session_id": "22222222-2222-4222-8222-222222222222",
        "user_metadata": {"plan": "trial"},
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1),
        "messages": [
            {
                "id": "33333333-3333-4333-8333-333333333333",
                "session_id": "22222222-2222-4222-8222-222222222222",
                "role": "user",
                "content": "How do I retain users?",
                "created_at": datetime(2024, 1, 1),
                "message_order": 1,
                "source_metadata": None,
            }
        ],
    }

    monkeypatch.setattr(main, "get_session", lambda session_id: session if session_id == session["session_id"] else None)

    response = client.get(f"/sessions/{session['session_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session["session_id"]
    assert payload["messages"][0]["content"] == "How do I retain users?"


def test_chat_uses_session_history_and_persists(monkeypatch):
    session_id = "44444444-4444-4444-8444-444444444444"
    existing_session = {
        "session_id": session_id,
        "user_metadata": {},
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1),
        "messages": [
            {
                "role": "user",
                "content": "What is onboarding?",
            },
            {
                "role": "assistant",
                "content": "Onboarding is critical.",
            },
        ],
    }

    monkeypatch.setattr(main, "get_session", lambda sid: existing_session if sid == session_id else None)
    monkeypatch.setattr(main, "save_message", lambda sid, role, content, source_metadata=None: {"ok": True})
    monkeypatch.setattr(main, "search", lambda query, top_k=3: [{
        "score": 0.75,
        "text": "Onboarding is the first experience that teaches users to value the product.",
        "source": {
            "guest": "Guest A",
            "title": "Episode A",
            "youtube_url": "https://example.com/a",
            "publish_date": "2024-03-01",
        },
    }])
    monkeypatch.setattr(
        main,
        "generate_answer",
        lambda **kwargs: main.AgentResponse(
            answer="Onboarding is the product setup experience.",
            sources=kwargs["sources"],
            provider="ollama",
            model="llama3.2:3b",
        ),
    )

    response = client.post("/chat", json={"message": "What about activation?", "session_id": session_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["provider"] == "ollama"
    assert "activation" in payload["answer"].lower() or "onboarding" in payload["answer"].lower()


def test_invalid_session_id_returns_structured_error(monkeypatch):
    monkeypatch.setattr(main, "get_session", lambda session_id: None)

    response = client.post("/chat", json={"message": "hi", "session_id": "not-a-uuid"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "validation_error"


def test_database_failure_returns_503(monkeypatch):
    def fail_create(*args, **kwargs):
        raise main.DatabaseUnavailableError("db down")

    monkeypatch.setattr(main, "create_session", fail_create)

    response = client.post("/sessions", json={"user_metadata": {"plan": "trial"}})

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"] == "database_unavailable"


def test_artifact_database_failure_returns_503(monkeypatch):
    monkeypatch.setattr(main, "get_session", lambda session_id: {"messages": []})
    monkeypatch.setattr(
        main,
        "generate_artifact",
        lambda **kwargs: type(
            "GeneratedArtifact",
            (),
            {
                "format": "markdown",
                "title": "Test artifact",
                "content": "# Test artifact",
                "provider": "ollama",
                "model": "llama3.2:3b",
                "sources": [],
            },
        )(),
    )
    monkeypatch.setattr(main, "create_artifact", lambda **kwargs: (_ for _ in ()).throw(main.DatabaseUnavailableError("db down")))

    response = client.post(
        "/artifacts",
        json={
            "session_id": "99999999-9999-4999-8999-999999999999",
            "prompt": "Create a visual HTML layout",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"] == "database_unavailable"


def test_unsupported_provider_returns_structured_error(monkeypatch):
    monkeypatch.setattr(main.settings, "llm_provider", "unsupported")

    response = client.post("/chat", json={"message": "hi"})

    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_provider"


def test_ship30_endpoint_invokes_skill_and_returns_metadata(monkeypatch):
    captured = {}
    results = [{
        "score": 0.88,
        "text": "Retention improves when the first value moment arrives quickly.",
        "source": {
            "guest": "Guest Ship",
            "title": "Shipping Better Onboarding",
            "youtube_url": "https://example.com/ship",
            "publish_date": "2024-02-01",
        },
    }]

    monkeypatch.setattr(main, "search", lambda query, top_k=3: results)

    def fake_skill(**kwargs):
        captured.update(kwargs)
        return main.Ship30SkillResponse(
            essay="# The First Value Moment\n\nA grounded essay.",
            skill_name="ship30_for_30",
            skill_version="1.0",
            provider="ollama",
            model="llama3.2:3b",
            sources=kwargs["sources"],
        )

    monkeypatch.setattr(main, "generate_ship30_essay", fake_skill)

    response = client.post("/skills/ship30", json={"message": "How can teams improve retention?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["skill_name"] == "ship30_for_30"
    assert payload["skill_version"] == "1.0"
    assert payload["provider"] == "ollama"
    assert payload["model"] == "llama3.2:3b"
    assert payload["sources"][0]["guest"] == "Guest Ship"
    assert captured["question"] == "How can teams improve retention?"
    assert "Retention improves" in captured["context"]


def test_ship30_insufficient_context_returns_existing_fallback(monkeypatch):
    monkeypatch.setattr(main, "search", lambda query, top_k=3: [])
    captured = {}

    def fallback_skill(**kwargs):
        captured.update(kwargs)
        return main.Ship30SkillResponse(
            essay="The available Lenny transcripts don't provide enough information to answer this.",
            skill_name="ship30_for_30",
            skill_version="1.0",
            provider="ollama",
            model="llama3.2:3b",
            sources=[],
        )

    monkeypatch.setattr(main, "generate_ship30_essay", fallback_skill)

    response = client.post("/skills/ship30", json={"message": "Write about an unknown topic"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["essay"] == "The available Lenny transcripts don't provide enough information to answer this."
    assert payload["sources"] == []
    assert captured["context"] == ""
    assert captured["sources"] == []


def test_artifact_request_validation_requires_session_and_supported_format():
    missing_session = client.post("/artifacts", json={"prompt": "Make a brief"})
    unsupported_format = client.post(
        "/artifacts",
        json={
            "session_id": "55555555-5555-4555-8555-555555555555",
            "prompt": "Make a brief",
            "format": "pdf",
        },
    )

    assert missing_session.status_code == 422
    assert unsupported_format.status_code == 422
    assert missing_session.json()["error"] == "validation_error"
    assert unsupported_format.json()["error"] == "validation_error"


def test_artifact_missing_session_returns_not_found(monkeypatch):
    monkeypatch.setattr(main, "get_session", lambda session_id: None)

    response = client.post(
        "/artifacts",
        json={
            "session_id": "66666666-6666-4666-8666-666666666666",
            "prompt": "Make a brief",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"] == "session_not_found"


def test_artifact_endpoint_generates_and_persists_with_session_context(monkeypatch):
    session_id = "77777777-7777-4777-8777-777777777777"
    session = {
        "session_id": session_id,
        "user_metadata": {},
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1),
        "messages": [{"role": "user", "content": "We discussed retention."}],
    }
    results = [{
        "score": 0.9,
        "text": "Retention improves when users reach value quickly.",
        "source": {
            "guest": "Guest Artifact",
            "title": "Retention Episode",
            "youtube_url": "https://example.com/retention",
            "publish_date": "2024-04-01",
        },
    }]
    captured = {}

    monkeypatch.setattr(main, "get_session", lambda value: session)
    monkeypatch.setattr(main, "search", lambda query, top_k=3: results)

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return type(
            "GeneratedArtifact",
            (),
            {
                "format": "markdown",
                "title": "Retention Brief",
                "content": "# Retention Brief",
                "provider": "ollama",
                "model": "llama3.2:3b",
                "sources": kwargs["sources"],
            },
        )()

    persisted = {
        "artifact_id": "88888888-8888-4888-8888-888888888888",
        "session_id": session_id,
        "format": "markdown",
        "title": "Retention Brief",
        "content": "# Retention Brief",
        "provider": "ollama",
        "model": "llama3.2:3b",
        "sources": [results[0]["source"]],
        "created_at": datetime(2024, 1, 1),
    }
    monkeypatch.setattr(main, "generate_artifact", fake_generate)
    monkeypatch.setattr(main, "create_artifact", lambda **kwargs: persisted)

    response = client.post(
        "/artifacts",
        json={
            "session_id": session_id,
            "prompt": "Create a retention brief from Lenny insights",
            "format": "markdown",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_id"] == persisted["artifact_id"]
    assert payload["title"] == "Retention Brief"
    assert payload["provider"] == "ollama"
    assert payload["sources"][0]["guest"] == "Guest Artifact"
    assert captured["history"] == session["messages"]
    assert "Retention improves" in captured["context"]