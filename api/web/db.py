"""web/db.py -- Postgres connection and queries for users and the chat session index."""
import os
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Json

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT DEFAULT '',
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    tier TEXT DEFAULT 'free',
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

CREATE TABLE IF NOT EXISTS visual_profiles (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    color_palette JSONB,
    typography_style TEXT,
    visual_mood TEXT,
    default_layout TEXT,
    platform_overrides JSONB,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS image_assets (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id TEXT,
    post_number INTEGER,
    mode TEXT NOT NULL DEFAULT 'text_to_image',
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    visual_profile_id TEXT REFERENCES visual_profiles(id) ON DELETE SET NULL,
    visual_brief_json JSONB,
    provider_name TEXT NOT NULL,
    model_name TEXT,
    generation_params JSONB,
    provider_metadata JSONB,
    reference_asset_id TEXT REFERENCES image_assets(id) ON DELETE SET NULL,
    source_post_version INTEGER DEFAULT 1,
    storage_backend TEXT NOT NULL DEFAULT 'local',
    storage_key TEXT NOT NULL,
    content_type TEXT DEFAULT 'image/png',
    file_size_bytes INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    rq_job_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_image_assets_session ON image_assets(session_id, post_number);
CREATE INDEX IF NOT EXISTS idx_image_assets_user ON image_assets(user_id);
"""


def _conn():
    return psycopg.connect(DATABASE_URL)


def ensure_default_visual_profile(conn=None) -> None:
    """Seed system default brand visual profile if it doesn't exist."""
    seed_sql = """
    INSERT INTO visual_profiles (
        id, user_id, name, description, color_palette, typography_style,
        visual_mood, default_layout, platform_overrides, is_default, created_at, updated_at
    ) VALUES (
        'default-trendforge-profile',
        NULL,
        'TrendForge Standard',
        'Default informative & clean visual identity',
        '{"primary": "#3B82F6", "secondary": "#10B981", "accent": "#F59E0B", "background": "#0F172A", "text": "#FFFFFF"}'::jsonb,
        'minimal-sans',
        'clean-informative',
        'minimal_clean',
        '{}'::jsonb,
        TRUE,
        now(),
        now()
    )
    ON CONFLICT (id) DO NOTHING;
    """
    if conn:
        conn.execute(seed_sql)
    else:
        with _conn() as c:
            c.execute(seed_sql)


def init_db() -> None:
    with _conn() as conn:
        conn.execute(_SCHEMA)
        # Migrate: ensure name & tier columns exist in users table if table was created earlier
        try:
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT DEFAULT '';")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'free';")
        except Exception:
            pass
        ensure_default_visual_profile(conn)


def parse_user_id(client_name: str) -> int:
    if not client_name.startswith("user:"):
        raise ValueError(f"not a user identity: {client_name}")
    return int(client_name.split(":", 1)[1])


def create_user(email: str, password_hash: str, name: Optional[str] = None, tier: str = "free") -> int:
    with _conn() as conn:
        row = conn.execute(
            "INSERT INTO users (email, password_hash, name, tier) VALUES (%s, %s, %s, %s) RETURNING id",
            (email, password_hash, name or "", tier or "free"),
        ).fetchone()
        return row[0]


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, COALESCE(name, ''), COALESCE(tier, 'free') FROM users WHERE email = %s", (email,)
        ).fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "password_hash": row[2], "name": row[3], "tier": row[4]}


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT id, email, COALESCE(name, ''), COALESCE(tier, 'free') FROM users WHERE id = %s", (user_id,)).fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "name": row[2], "tier": row[3]}


def update_user_tier(user_id: int, tier: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET tier = %s WHERE id = %s", (tier, user_id))


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


# ─────────────────────────────────────────────────────────────────────────────
# Visual Profiles CRUD
# ─────────────────────────────────────────────────────────────────────────────

def create_visual_profile_in_db(profile_data: Dict[str, Any]) -> str:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO visual_profiles (
                id, user_id, name, description, color_palette, typography_style,
                visual_mood, default_layout, platform_overrides, is_default, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                color_palette = EXCLUDED.color_palette,
                typography_style = EXCLUDED.typography_style,
                visual_mood = EXCLUDED.visual_mood,
                default_layout = EXCLUDED.default_layout,
                platform_overrides = EXCLUDED.platform_overrides,
                is_default = EXCLUDED.is_default,
                updated_at = now()
            """,
            (
                profile_data["id"],
                profile_data.get("user_id"),
                profile_data["name"],
                profile_data.get("description", ""),
                Json(profile_data.get("color_palette") or {}),
                profile_data.get("typography_style", "minimal-sans"),
                profile_data.get("visual_mood", "clean-informative"),
                profile_data.get("default_layout", "minimal_clean"),
                Json(profile_data.get("platform_overrides") or {}),
                profile_data.get("is_default", False),
            ),
        )
        return profile_data["id"]


def get_visual_profile_from_db(profile_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, name, description, color_palette, typography_style,
                   visual_mood, default_layout, platform_overrides, is_default, created_at, updated_at
            FROM visual_profiles WHERE id = %s
            """,
            (profile_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "name": row[2],
            "description": row[3],
            "color_palette": row[4],
            "typography_style": row[5],
            "visual_mood": row[6],
            "default_layout": row[7],
            "platform_overrides": row[8],
            "is_default": row[9],
            "created_at": row[10].isoformat() if row[10] else None,
            "updated_at": row[11].isoformat() if row[11] else None,
        }


def list_visual_profiles_from_db(user_id: int) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, name, description, color_palette, typography_style,
                   visual_mood, default_layout, platform_overrides, is_default, created_at, updated_at
            FROM visual_profiles
            WHERE user_id = %s OR is_default = TRUE
            ORDER BY is_default DESC, created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "user_id": r[1],
                "name": r[2],
                "description": r[3],
                "color_palette": r[4],
                "typography_style": r[5],
                "visual_mood": r[6],
                "default_layout": r[7],
                "platform_overrides": r[8],
                "is_default": r[9],
                "created_at": r[10].isoformat() if r[10] else None,
                "updated_at": r[11].isoformat() if r[11] else None,
            }
            for r in rows
        ]


def update_visual_profile_in_db(profile_id: str, updates: Dict[str, Any]) -> bool:
    with _conn() as conn:
        set_clauses = []
        values = []
        for k, v in updates.items():
            if k in ("color_palette", "platform_overrides"):
                set_clauses.append(f"{k} = %s")
                values.append(Json(v))
            elif k in ("name", "description", "typography_style", "visual_mood", "default_layout", "is_default"):
                set_clauses.append(f"{k} = %s")
                values.append(v)
        if not set_clauses:
            return False
        set_clauses.append("updated_at = now()")
        values.append(profile_id)
        query = f"UPDATE visual_profiles SET {', '.join(set_clauses)} WHERE id = %s"
        res = conn.execute(query, tuple(values))
        return res.rowcount > 0


def delete_visual_profile_from_db(profile_id: str) -> bool:
    with _conn() as conn:
        res = conn.execute("DELETE FROM visual_profiles WHERE id = %s", (profile_id,))
        return res.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# Image Assets CRUD
# ─────────────────────────────────────────────────────────────────────────────

def create_image_asset_in_db(asset_data: Dict[str, Any]) -> str:
    profile_id = asset_data.get("visual_profile_id")
    with _conn() as conn:
        if profile_id:
            if profile_id == "default-trendforge-profile":
                ensure_default_visual_profile(conn)
            else:
                exists = conn.execute(
                    "SELECT 1 FROM visual_profiles WHERE id = %s", (profile_id,)
                ).fetchone()
                if not exists:
                    profile_id = None

        conn.execute(
            """
            INSERT INTO image_assets (
                id, user_id, session_id, post_number, mode, prompt, negative_prompt,
                visual_profile_id, visual_brief_json, provider_name, model_name,
                generation_params, provider_metadata, reference_asset_id,
                source_post_version, storage_backend, storage_key, content_type,
                file_size_bytes, status, error_message, rq_job_id, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now()
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                file_size_bytes = COALESCE(EXCLUDED.file_size_bytes, image_assets.file_size_bytes),
                storage_key = COALESCE(EXCLUDED.storage_key, image_assets.storage_key),
                provider_metadata = COALESCE(EXCLUDED.provider_metadata, image_assets.provider_metadata),
                error_message = EXCLUDED.error_message,
                updated_at = now()
            """,
            (
                asset_data["id"],
                asset_data.get("user_id"),
                asset_data.get("session_id", ""),
                asset_data.get("post_number", 1),
                asset_data.get("mode", "text_to_image"),
                asset_data.get("prompt", ""),
                asset_data.get("negative_prompt", ""),
                profile_id,
                Json(asset_data.get("visual_brief") or {}) if asset_data.get("visual_brief") else None,
                asset_data.get("provider_name", "mock"),
                asset_data.get("model_name", ""),
                Json(asset_data.get("generation_params") or {}),
                Json(asset_data.get("provider_metadata") or {}),
                asset_data.get("reference_asset_id"),
                asset_data.get("source_post_version", 1),
                asset_data.get("storage_backend", "local"),
                asset_data.get("storage_key", ""),
                asset_data.get("content_type", "image/png"),
                asset_data.get("file_size_bytes"),
                asset_data.get("status", "pending"),
                asset_data.get("error_message"),
                asset_data.get("rq_job_id"),
            ),
        )
        return asset_data["id"]


def get_image_asset_from_db(asset_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, session_id, post_number, mode, prompt, negative_prompt,
                   visual_profile_id, visual_brief_json, provider_name, model_name,
                   generation_params, provider_metadata, reference_asset_id,
                   source_post_version, storage_backend, storage_key, content_type,
                   file_size_bytes, status, error_message, rq_job_id, created_at, updated_at
            FROM image_assets WHERE id = %s
            """,
            (asset_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "session_id": row[2],
            "post_number": row[3],
            "mode": row[4],
            "prompt": row[5],
            "negative_prompt": row[6],
            "visual_profile_id": row[7],
            "visual_brief": row[8],
            "provider_name": row[9],
            "model_name": row[10],
            "generation_params": row[11],
            "provider_metadata": row[12],
            "reference_asset_id": row[13],
            "source_post_version": row[14],
            "storage_backend": row[15],
            "storage_key": row[16],
            "content_type": row[17],
            "file_size_bytes": row[18],
            "status": row[19],
            "error_message": row[20],
            "rq_job_id": row[21],
            "created_at": row[22].isoformat() if row[22] else None,
            "updated_at": row[23].isoformat() if row[23] else None,
        }


def update_image_asset_status_in_db(
    asset_id: str,
    status: str,
    error_message: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    storage_key: Optional[str] = None,
    provider_metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    with _conn() as conn:
        set_clauses = ["status = %s", "updated_at = now()"]
        values: List[Any] = [status]

        if error_message is not None:
            set_clauses.append("error_message = %s")
            values.append(error_message)
        if file_size_bytes is not None:
            set_clauses.append("file_size_bytes = %s")
            values.append(file_size_bytes)
        if storage_key is not None:
            set_clauses.append("storage_key = %s")
            values.append(storage_key)
        if provider_metadata is not None:
            set_clauses.append("provider_metadata = %s")
            values.append(Json(provider_metadata))

        values.append(asset_id)
        query = f"UPDATE image_assets SET {', '.join(set_clauses)} WHERE id = %s"
        res = conn.execute(query, tuple(values))
        return res.rowcount > 0


def list_image_assets_for_session_from_db(session_id: str) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, session_id, post_number, mode, prompt,
                   visual_profile_id, provider_name, model_name,
                   reference_asset_id, source_post_version, storage_backend,
                   storage_key, content_type, file_size_bytes, status, error_message,
                   created_at, updated_at
            FROM image_assets
            WHERE session_id = %s
            ORDER BY post_number ASC, created_at DESC
            """,
            (session_id,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "user_id": r[1],
                "session_id": r[2],
                "post_number": r[3],
                "mode": r[4],
                "prompt": r[5],
                "visual_profile_id": r[6],
                "provider_name": r[7],
                "model_name": r[8],
                "reference_asset_id": r[9],
                "source_post_version": r[10],
                "storage_backend": r[11],
                "storage_key": r[12],
                "content_type": r[13],
                "file_size_bytes": r[14],
                "status": r[15],
                "error_message": r[16],
                "created_at": r[17].isoformat() if r[17] else None,
                "updated_at": r[18].isoformat() if r[18] else None,
            }
            for r in rows
        ]
