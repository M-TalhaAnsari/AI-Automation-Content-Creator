"""web/db.py -- Postgres connection and queries for users and the chat session index."""
import os
from typing import Optional, List, Dict, Any

import psycopg
from psycopg.types.json import Json

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    title TEXT,
    conversation_json JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_active_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, session_id)
);
"""


def _conn():
    return psycopg.connect(DATABASE_URL)


def init_db() -> None:
    with _conn() as conn:
        conn.execute(_SCHEMA)


def parse_user_id(client_name: str) -> int:
    if not client_name.startswith("user:"):
        raise ValueError(f"not a user identity: {client_name}")
    return int(client_name.split(":", 1)[1])


def create_user(email: str, password_hash: str) -> int:
    with _conn() as conn:
        row = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
            (email, password_hash),
        ).fetchone()
        return row[0]


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = %s", (email,)
        ).fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "password_hash": row[2]}


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT id, email FROM users WHERE id = %s", (user_id,)).fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1]}


def upsert_chat_session(user_id: int, session_id: str, title: Optional[str] = None) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO chat_sessions (user_id, session_id, title, last_active_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (user_id, session_id)
            DO UPDATE SET last_active_at = now(),
                          title = COALESCE(chat_sessions.title, EXCLUDED.title)
            """,
            (user_id, session_id, title),
        )


def list_chat_sessions(user_id: int) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT session_id, title, created_at, last_active_at
            FROM chat_sessions
            WHERE user_id = %s
            ORDER BY last_active_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [
            {
                "session_id": r[0],
                "title": r[1],
                "created_at": r[2].isoformat(),
                "last_active_at": r[3].isoformat(),
            }
            for r in rows
        ]


def save_conversation_to_db(user_id: int, session_id: str, conversation: Dict[str, Any]) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO chat_sessions (user_id, session_id, conversation_json, last_active_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (user_id, session_id)
            DO UPDATE SET conversation_json = EXCLUDED.conversation_json,
                          last_active_at = now()
            """,
            (user_id, session_id, Json(conversation)),
        )


def delete_chat_session(user_id: int, session_id: str) -> None:
    with _conn() as conn:
        conn.execute(
            "DELETE FROM chat_sessions WHERE user_id = %s AND session_id = %s",
            (user_id, session_id),
        )


def load_conversation_from_db(user_id: int, session_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT conversation_json FROM chat_sessions WHERE user_id = %s AND session_id = %s",
            (user_id, session_id),
        ).fetchone()
        if not row or row[0] is None:
            return None
        return row[0]