import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from .settings import settings


logger = logging.getLogger("lenny_growth_assistant.database")
_SCHEMA_READY = False


class DatabaseUnavailableError(RuntimeError):
    """Raised when the configured database is not available."""


def get_connection():
    """Create a database connection using the configured settings."""
    if not settings.database_url:
        raise DatabaseUnavailableError("Database is not configured.")

    try:
        conn = psycopg.connect(
            settings.database_url,
            row_factory=dict_row,
            connect_timeout=settings.database_connect_timeout_seconds,
        )
        conn.autocommit = False
        return conn
    except Exception as exc:  # pragma: no cover - defensive runtime check
        logger.warning("database_connection_failed error_type=%s", type(exc).__name__)
        raise DatabaseUnavailableError("Database is temporarily unavailable.") from exc


def ensure_schema():
    """Create the required session and message tables if they are missing."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id UUID PRIMARY KEY,
                    user_metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id UUID PRIMARY KEY,
                    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    source_metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    message_order INTEGER NOT NULL
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session_order ON messages (session_id, message_order)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions (updated_at)"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id UUID PRIMARY KEY,
                    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    format VARCHAR(20) NOT NULL CHECK (format IN ('markdown', 'html')),
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    model VARCHAR(200) NOT NULL,
                    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifacts_session_created ON artifacts (session_id, created_at DESC)"
            )
        conn.commit()
        _SCHEMA_READY = True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_session(user_metadata=None):
    """Create a new conversation session and return its metadata."""
    ensure_schema()
    session_id = str(uuid4())
    metadata = user_metadata or {}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (id, user_metadata, created_at, updated_at)
                VALUES (%s, %s::jsonb, NOW(), NOW())
                RETURNING id, user_metadata, created_at, updated_at
                """,
                (session_id, json.dumps(metadata)),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "session_id": str(row["id"]),
        "user_metadata": row["user_metadata"] or {},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "messages": [],
    }


def _serialize_message_row(row):
    return {
        "id": str(row["id"]),
        "session_id": str(row["session_id"]),
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
        "message_order": row["message_order"],
        "source_metadata": row["source_metadata"],
    }


def get_session(session_id: str):
    """Fetch a session and all related messages in insertion order."""
    ensure_schema()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_metadata, created_at, updated_at
                FROM sessions
                WHERE id = %s
                """,
                (session_id,),
            )
            session_row = cur.fetchone()
            if not session_row:
                return None

            cur.execute(
                """
                SELECT id, session_id, role, content, source_metadata, created_at, message_order
                FROM messages
                WHERE session_id = %s
                ORDER BY message_order ASC, created_at ASC
                """,
                (session_id,),
            )
            messages = [_serialize_message_row(row) for row in cur.fetchall()]

        return {
            "session_id": str(session_row["id"]),
            "user_metadata": session_row["user_metadata"] or {},
            "created_at": session_row["created_at"],
            "updated_at": session_row["updated_at"],
            "messages": messages,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_message(session_id: str, role: str, content: str, source_metadata=None):
    """Persist a single message and update the session timestamp."""
    ensure_schema()
    message_id = str(uuid4())
    payload = json.dumps(source_metadata) if source_metadata is not None else None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(message_order), 0) + 1 AS next_order FROM messages WHERE session_id = %s",
                (session_id,),
            )
            next_order = cur.fetchone()["next_order"]
            cur.execute(
                """
                INSERT INTO messages (id, session_id, role, content, source_metadata, created_at, message_order)
                VALUES (%s, %s, %s, %s, %s::jsonb, NOW(), %s)
                RETURNING id, session_id, role, content, source_metadata, created_at, message_order
                """,
                (message_id, session_id, role, content, payload, next_order),
            )
            inserted_row = cur.fetchone()
            cur.execute(
                "UPDATE sessions SET updated_at = NOW() WHERE id = %s",
                (session_id,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return _serialize_message_row(inserted_row)


def get_session_messages(session_id: str):
    """Return message history for a session, in display order."""
    session = get_session(session_id)
    if session is None:
        return []
    return session["messages"]


def create_artifact(
    session_id: str,
    artifact_format: str,
    title: str,
    content: str,
    provider: str,
    model: str,
    sources=None,
):
    """Persist a generated artifact and return its API representation."""
    ensure_schema()
    artifact_id = str(uuid4())

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO artifacts
                    (id, session_id, format, title, content, provider, model, sources, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                RETURNING id, session_id, format, title, content, provider, model, sources, created_at
                """,
                (
                    artifact_id,
                    session_id,
                    artifact_format,
                    title,
                    content,
                    provider,
                    model,
                    json.dumps(sources or []),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "artifact_id": str(row["id"]),
        "session_id": str(row["session_id"]),
        "format": row["format"],
        "title": row["title"],
        "content": row["content"],
        "provider": row["provider"],
        "model": row["model"],
        "sources": row["sources"] or [],
        "created_at": row["created_at"],
    }
