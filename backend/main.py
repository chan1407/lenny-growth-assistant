from datetime import datetime
import logging
import time
from typing import Any, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import ollama
from agent import AgentResponse, generate_answer
from artifact import (
    UnsupportedArtifactFormatError,
    UnsupportedArtifactProviderError,
    generate_artifact,
    should_retrieve,
)
from db import DatabaseUnavailableError, create_artifact, create_session, get_session, save_message
from providers import MissingCredentialsError, ProviderUnavailableError, SUPPORTED_PROVIDERS
from settings import settings
from retriever import search
from skills.ship30 import (
    Ship30Response as Ship30SkillResponse,
    UnsupportedSkillProviderError,
    generate_ship30_essay,
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Question to answer from Lenny transcripts")
    session_id: UUID | None = Field(default=None, description="Optional active chat session ID")


class SessionCreateRequest(BaseModel):
    user_metadata: dict[str, Any] | None = Field(default=None, description="Optional session metadata")


class SessionMessage(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime
    message_order: int
    source_metadata: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    session_id: str
    user_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    messages: list[SessionMessage] = Field(default_factory=list)


class SourceInfo(BaseModel):
    guest: str | None = None
    title: str | None = None
    youtube_url: str | None = None
    publish_date: str | None = None


class SearchResult(BaseModel):
    score: float
    text: str
    source: SourceInfo


class ChatResponse(BaseModel):
    session_id: str | None = None
    answer: str
    sources: list[SourceInfo]
    provider: str
    model: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class Ship30Request(BaseModel):
    message: str = Field(..., min_length=1, description="Question or angle for the Ship 30 for 30 essay")
    session_id: UUID | None = Field(default=None, description="Optional active chat session ID")


class Ship30Response(BaseModel):
    essay: str
    skill_name: str
    skill_version: str
    provider: str
    model: str
    sources: list[SourceInfo]


class ArtifactRequest(BaseModel):
    session_id: UUID
    prompt: str = Field(..., min_length=1, max_length=12000)
    format: Literal["markdown", "html"] = "markdown"


class ArtifactResponse(BaseModel):
    artifact_id: str
    session_id: str
    format: Literal["markdown", "html"]
    title: str
    content: str
    provider: str
    model: str
    sources: list[SourceInfo]
    created_at: datetime


class OllamaHealth(BaseModel):
    configured: bool
    model: str | None = None
    base_url: str | None = None
    reachable: bool | None = None


class DatabaseHealth(BaseModel):
    configured: bool


class LLMHealth(BaseModel):
    provider: str
    model: str
    configured: bool


class HealthResponse(BaseModel):
    status: str
    application: str
    ollama: OllamaHealth
    database: DatabaseHealth
    llm: LLMHealth


app = FastAPI(title="Lenny Growth Assistant")
logger = logging.getLogger("lenny_growth_assistant")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "request_complete method=%s path=%s status=%s latency_ms=%s",
            request.method,
            request.url.path,
            response.status_code if response else 500,
            elapsed_ms,
        )


def _error_payload(code: str, message: str, detail: Any | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": code,
        "message": message,
    }
    if detail is not None:
        payload["detail"] = detail
    return payload


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_error_payload("validation_error", "Request validation failed.", exc.errors()),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        error_code = detail.get("error", "http_error")
        message = detail.get("message", "An HTTP error occurred.")
        payload = _error_payload(error_code, message, detail.get("detail"))
    else:
        payload = _error_payload("http_error", str(detail))
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=_error_payload("internal_server_error", "An unexpected server error occurred."),
    )


def _database_unavailable_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": "database_unavailable",
            "message": "The database is temporarily unavailable.",
        },
    )


def _not_found_error(entity: str, value: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": f"{entity}_not_found",
            "message": f"{entity.capitalize()} '{value}' was not found.",
        },
    )


def _build_ollama_client(timeout: float | None = None):
    return ollama.Client(
        host=settings.ollama_base_url,
        timeout=timeout if timeout is not None else settings.ollama_timeout_seconds,
    )


def _active_model() -> str:
    if settings.llm_provider == "anthropic":
        return settings.anthropic_model
    return settings.ollama_model


def _provider_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MissingCredentialsError):
        code = "provider_credentials_missing"
        message = str(exc)
    elif isinstance(exc, ProviderUnavailableError):
        code = "provider_unavailable"
        message = str(exc)
    else:
        code = "provider_error"
        message = "The configured LLM provider could not complete the request."
    return HTTPException(status_code=503, detail={"error": code, "message": message})


def _validate_provider():
    if settings.llm_provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_provider",
                "message": f"Unsupported LLM provider '{settings.llm_provider}'.",
            },
        )


@app.get("/", response_model=dict[str, str])
def root():
    return {"message": "Lenny Growth Assistant API"}


@app.get("/health", response_model=HealthResponse)
def health():
    ollama_status = OllamaHealth(
        configured=settings.ollama_configured,
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        reachable=False,
    )

    try:
        if settings.llm_provider == "ollama":
            _build_ollama_client(settings.ollama_health_timeout_seconds).list()
        ollama_status.reachable = True
    except Exception:
        ollama_status.reachable = False

    return HealthResponse(
        status="ok",
        application="ok",
        ollama=ollama_status,
        database=DatabaseHealth(configured=settings.database_configured),
        llm=LLMHealth(
            provider=settings.llm_provider,
            model=_active_model(),
            configured=(
                settings.ollama_configured
                if settings.llm_provider == "ollama"
                else settings.anthropic_configured
            ),
        ),
    )


@app.get("/health/live")
def health_live():
    return {"status": "ok", "application": "alive"}


@app.get("/health/ready")
def health_ready():
    database_reachable = False
    try:
        from db import get_connection

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        database_reachable = True
    except Exception as exc:
        logger.warning("readiness_database_failed error_type=%s", type(exc).__name__)

    ollama_reachable = None
    if settings.llm_provider == "ollama":
        try:
            _build_ollama_client(settings.ollama_health_timeout_seconds).list()
            ollama_reachable = True
        except Exception as exc:
            ollama_reachable = False
            logger.warning("readiness_ollama_failed error_type=%s", type(exc).__name__)

    provider_ready = (
        settings.ollama_configured and ollama_reachable is True
        if settings.llm_provider == "ollama"
        else settings.anthropic_configured
    )
    ready = database_reachable and provider_ready
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "database": {"configured": settings.database_configured, "reachable": database_reachable},
            "llm": {
                "provider": settings.llm_provider,
                "model": _active_model(),
                "configured": provider_ready,
                "reachable": ollama_reachable,
            },
        },
    )


@app.post("/sessions", response_model=SessionResponse)
def create_session_endpoint(request: SessionCreateRequest):
    try:
        session = create_session(request.user_metadata or {})
    except DatabaseUnavailableError:
        raise _database_unavailable_error() from None
    except Exception:
        raise _database_unavailable_error() from None

    return SessionResponse(**session)


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session_endpoint(session_id: UUID):
    try:
        session = get_session(str(session_id))
    except DatabaseUnavailableError:
        raise _database_unavailable_error() from None
    except Exception:
        raise _database_unavailable_error() from None

    if session is None:
        raise _not_found_error("session", str(session_id))

    return SessionResponse(**session)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = str(request.session_id) if request.session_id is not None else None
    history: list[dict[str, Any]] = []

    _validate_provider()

    if session_id:
        try:
            session = get_session(session_id)
        except DatabaseUnavailableError:
            raise _database_unavailable_error() from None
        except Exception:
            raise _database_unavailable_error() from None

        if session is None:
            raise _not_found_error("session", session_id)
        history = session.get("messages", [])

    results = search(request.message, top_k=3)
    logger.info("chat_retrieval provider=%s model=%s retrieval_count=%s", settings.llm_provider, _active_model(), len(results))

    if not results:
        answer = "The available Lenny transcripts don't provide enough information to answer this."
        if session_id:
            try:
                save_message(session_id, "user", request.message)
                save_message(session_id, "assistant", answer, {"sources": []})
            except DatabaseUnavailableError:
                raise _database_unavailable_error() from None
            except Exception:
                raise _database_unavailable_error() from None
        return ChatResponse(
            session_id=session_id,
            answer=answer,
            sources=[],
            provider=settings.llm_provider,
            model=_active_model(),
        )

    context = "\n\n".join(
        [
            f"[SOURCE {i + 1}]\n"
            f"Guest: {result['source']['guest']}\n"
            f"Title: {result['source']['title']}\n"
            f"Transcript:\n{result['text'][:4000]}"
            for i, result in enumerate(results)
        ]
    )

    try:
        generation: AgentResponse = generate_answer(
            question=request.message,
            context=context,
            sources=[result["source"] for result in results],
            history=history,
        )
    except (ProviderUnavailableError, MissingCredentialsError) as exc:
        raise _provider_error(exc) from None
    except RuntimeError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_provider", "message": str(exc)},
        ) from None

    if session_id:
        try:
            save_message(session_id, "user", request.message)
            save_message(
                session_id,
                "assistant",
                generation.answer,
                {"sources": [result["source"] for result in results]},
            )
        except DatabaseUnavailableError:
            raise _database_unavailable_error() from None
        except Exception:
            raise _database_unavailable_error() from None

    return ChatResponse(
        session_id=session_id,
        answer=generation.answer,
        sources=[SourceInfo(**result["source"]) for result in results],
        provider=generation.provider,
        model=generation.model,
    )


@app.post("/skills/ship30", response_model=Ship30Response)
def ship30(request: Ship30Request):
    session_id = str(request.session_id) if request.session_id is not None else None
    history: list[dict[str, Any]] = []

    _validate_provider()

    if session_id:
        try:
            session = get_session(session_id)
        except DatabaseUnavailableError:
            raise _database_unavailable_error() from None
        except Exception:
            raise _database_unavailable_error() from None
        if session is None:
            raise _not_found_error("session", session_id)
        history = session.get("messages", [])

    results = search(request.message, top_k=3)
    logger.info("ship30_generation provider=%s model=%s retrieval_count=%s", settings.llm_provider, _active_model(), len(results))
    context = "\n\n".join(
        f"[SOURCE {index + 1}]\n"
        f"Guest: {result['source']['guest']}\n"
        f"Title: {result['source']['title']}\n"
        f"Transcript:\n{result['text'][:4000]}"
        for index, result in enumerate(results)
    )

    try:
        generated: Ship30SkillResponse = generate_ship30_essay(
            question=request.message,
            context=context,
            sources=[result["source"] for result in results],
            history=history,
        )
    except (ProviderUnavailableError, MissingCredentialsError) as exc:
        raise _provider_error(exc) from None
    except UnsupportedSkillProviderError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_provider", "message": str(exc)},
        ) from None

    if session_id:
        try:
            save_message(session_id, "user", request.message)
            save_message(
                session_id,
                "assistant",
                generated.essay,
                {
                    "skill_name": generated.skill_name,
                    "skill_version": generated.skill_version,
                    "sources": generated.sources,
                },
            )
        except DatabaseUnavailableError:
            raise _database_unavailable_error() from None
        except Exception:
            raise _database_unavailable_error() from None

    return Ship30Response(
        essay=generated.essay,
        skill_name=generated.skill_name,
        skill_version=generated.skill_version,
        provider=generated.provider,
        model=generated.model,
        sources=[SourceInfo(**source) for source in generated.sources],
    )


@app.post("/artifacts", response_model=ArtifactResponse)
def create_artifact_endpoint(request: ArtifactRequest):
    session_id = str(request.session_id)

    _validate_provider()

    try:
        session = get_session(session_id)
    except DatabaseUnavailableError:
        raise _database_unavailable_error() from None
    except Exception:
        raise _database_unavailable_error() from None

    if session is None:
        raise _not_found_error("session", session_id)

    history = session.get("messages", [])
    results = search(request.prompt, top_k=3) if should_retrieve(request.prompt, history) else []
    logger.info(
        "artifact_generation provider=%s model=%s format=%s retrieval_count=%s session_id=%s",
        settings.llm_provider,
        _active_model(),
        request.format,
        len(results),
        session_id,
    )
    context = "\n\n".join(
        f"[SOURCE {index + 1}]\n"
        f"Guest: {result['source']['guest']}\n"
        f"Title: {result['source']['title']}\n"
        f"Transcript:\n{result['text'][:4000]}"
        for index, result in enumerate(results)
    )

    try:
        generated = generate_artifact(
            prompt=request.prompt,
            artifact_format=request.format,
            context=context,
            sources=[result["source"] for result in results],
            history=history,
        )
    except UnsupportedArtifactFormatError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "unsupported_artifact_format", "message": str(exc)},
        ) from None
    except UnsupportedArtifactProviderError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_provider", "message": str(exc)},
        ) from None
    except (ProviderUnavailableError, MissingCredentialsError) as exc:
        raise _provider_error(exc) from None

    try:
        persisted = create_artifact(
            session_id=session_id,
            artifact_format=generated.format,
            title=generated.title,
            content=generated.content,
            provider=generated.provider,
            model=generated.model,
            sources=generated.sources,
        )
    except DatabaseUnavailableError:
        raise _database_unavailable_error() from None
    except Exception:
        raise _database_unavailable_error() from None

    return ArtifactResponse(
        artifact_id=persisted["artifact_id"],
        session_id=persisted["session_id"],
        format=persisted["format"],
        title=persisted["title"],
        content=persisted["content"],
        provider=persisted["provider"],
        model=persisted["model"],
        sources=[SourceInfo(**source) for source in persisted["sources"]],
        created_at=persisted["created_at"],
    )


@app.get("/search", response_model=SearchResponse)
def search_knowledge(
    q: str = Query(..., min_length=1, description="Search query to answer using transcript knowledge"),
    top_k: int = Query(5, ge=1, le=10),
):
    results = search(q, top_k)

    return SearchResponse(
        query=q,
        results=[
            SearchResult(
                score=float(result["score"]),
                text=result["text"],
                source=SourceInfo(**result["source"]),
            )
            for result in results
        ],
    )
