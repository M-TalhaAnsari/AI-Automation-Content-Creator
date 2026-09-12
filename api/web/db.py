"""api/web/db.py -- Production-grade Postgres schema and query layer.

Schema v2:
  - users: email/password and Google OAuth, tier, avatar, provider tracking
  - refresh_tokens: opaque token rotation with family-based theft detection
  - user_daily_usage: post/image quota enforcement per calendar day (UTC)
  - chat_sessions, visual_profiles, image_assets, user_preferences: unchanged
"""
import hashlib
import os
import secrets
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Json

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# Schema DDL — idempotent, safe to run on every startup
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT DEFAULT '',
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    google_id TEXT,
    avatar_url TEXT,
    provider TEXT NOT NULL DEFAULT 'email',
    is_email_verified BOOLEAN DEFAULT FALSE,
    tier TEXT NOT NULL DEFAULT 'free',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    family TEXT NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    user_agent TEXT DEFAULT '',
    ip_address TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family  ON refresh_tokens(family);

CREATE TABLE IF NOT EXISTS user_daily_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    posts_generated INTEGER NOT NULL DEFAULT 0,
    images_generated INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, usage_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_usage_user_date ON user_daily_usage(user_id, usage_date);

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
CREATE INDEX IF NOT EXISTS idx_image_assets_user    ON image_assets(user_id);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    brand_name TEXT DEFAULT '',
    brand_handle TEXT DEFAULT '@aiflick',
    target_audience TEXT DEFAULT '',
    tone_of_voice TEXT DEFAULT 'punchy, authoritative, high-conversion',
    custom_rules TEXT DEFAULT '',
    show_watermark BOOLEAN DEFAULT TRUE,
    preferred_model_tier TEXT DEFAULT 'free',
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_uploaded_assets (
    id VARCHAR(64) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    mime_type VARCHAR(64) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    asset_role VARCHAR(32) NOT NULL DEFAULT 'avatar',
    default_scope VARCHAR(32) NOT NULL DEFAULT 'all',
    storage_key TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_assets_user_id ON user_uploaded_assets(user_id);
"""

# ---------------------------------------------------------------------------
# Migration helpers — add columns/tables that may not exist on older DBs
# ---------------------------------------------------------------------------

_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT DEFAULT '';",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'free';",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS provider TEXT DEFAULT 'email';",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();",
    # Make password_hash nullable for Google-only accounts
    "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;",
    # Ensure google_id uniqueness (partial index to allow multiple NULLs)
    "CREATE UNIQUE INDEX IF NOT EXISTS users_google_id_unique ON users(google_id) WHERE google_id IS NOT NULL;",
    """CREATE TABLE IF NOT EXISTS user_uploaded_assets (
        id VARCHAR(64) PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        mime_type VARCHAR(64) NOT NULL,
        file_size_bytes INTEGER NOT NULL,
        asset_role VARCHAR(32) NOT NULL DEFAULT 'avatar',
        default_scope VARCHAR(32) NOT NULL DEFAULT 'all',
        storage_key TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now()
    );""",
    "CREATE INDEX IF NOT EXISTS idx_user_assets_user_id ON user_uploaded_assets(user_id);",
]


def _conn():
    return psycopg.connect(DATABASE_URL)


def init_db() -> None:
    with _conn() as conn:
        conn.execute(_SCHEMA)
        for sql in _MIGRATIONS:
            try:
                conn.execute(sql)
            except Exception:
                pass
        ensure_default_visual_profile(conn)


def parse_user_id(client_name: str) -> int:
    if not client_name.startswith("user:"):
        raise ValueError(f"not a user identity: {client_name}")
    return int(client_name.split(":", 1)[1])


# ---------------------------------------------------------------------------
# Users CRUD
# ---------------------------------------------------------------------------

def create_user(
    email: str,
    password_hash: Optional[str] = None,
    name: Optional[str] = None,
    tier: str = "free",
    google_id: Optional[str] = None,
    avatar_url: Optional[str] = None,
    provider: str = "email",
    is_email_verified: bool = False,
) -> int:
    with _conn() as conn:
        row = conn.execute(
            """
            INSERT INTO users
                (email, password_hash, name, tier, google_id, avatar_url, provider, is_email_verified)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (email, password_hash, name or "", tier or "free", google_id, avatar_url, provider, is_email_verified),
        ).fetchone()
        return row[0]


def _user_row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
        "name": row[3],
        "tier": row[4],
        "google_id": row[5],
        "avatar_url": row[6],
        "provider": row[7],
        "is_email_verified": row[8],
    }


_USER_SELECT = """
    SELECT id, email, password_hash, COALESCE(name, ''), COALESCE(tier, 'free'),
           google_id, avatar_url, COALESCE(provider, 'email'), COALESCE(is_email_verified, FALSE)
    FROM users
"""


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(f"{_USER_SELECT} WHERE email = %s", (email,)).fetchone()
        return _user_row_to_dict(row) if row else None


def get_user_by_google_id(google_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(f"{_USER_SELECT} WHERE google_id = %s", (google_id,)).fetchone()
        return _user_row_to_dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(f"{_USER_SELECT} WHERE id = %s", (user_id,)).fetchone()
        return _user_row_to_dict(row) if row else None


def upsert_user_google(
    google_id: str,
    email: str,
    name: str,
    avatar_url: Optional[str],
) -> Dict[str, Any]:
    """
    Find existing user by google_id or email, link Google account, update profile.
    Returns the full user dict. Never creates a duplicate email row.
    Thread-safe via single DB transaction.
    """
    with _conn() as conn:
        # 1. Check by google_id first (returning user via Google)
        existing = conn.execute(
            "SELECT id FROM users WHERE google_id = %s", (google_id,)
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE users
                SET name = COALESCE(NULLIF(%s, ''), name),
                    avatar_url = COALESCE(%s, avatar_url),
                    last_login_at = now(),
                    updated_at = now()
                WHERE id = %s
                """,
                (name, avatar_url, existing[0]),
            )
            user_id = existing[0]
        else:
            # 2. Try to find by email (might be an existing email user linking Google)
            by_email = conn.execute(
                "SELECT id FROM users WHERE email = %s", (email,)
            ).fetchone()

            if by_email:
                conn.execute(
                    """
                    UPDATE users
                    SET google_id = %s,
                        avatar_url = COALESCE(%s, avatar_url),
                        name = COALESCE(NULLIF(%s, ''), name),
                        is_email_verified = TRUE,
                        provider = 'google',
                        last_login_at = now(),
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (google_id, avatar_url, name, by_email[0]),
                )
                user_id = by_email[0]
            else:
                # 3. Brand new Google user
                row = conn.execute(
                    """
                    INSERT INTO users
                        (email, google_id, name, avatar_url, provider, is_email_verified, tier)
                    VALUES (%s, %s, %s, %s, 'google', TRUE, 'free')
                    RETURNING id
                    """,
                    (email, google_id, name, avatar_url),
                ).fetchone()
                user_id = row[0]

    return get_user_by_id(user_id)


def update_user_tier(user_id: int, tier: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET tier = %s, updated_at = now() WHERE id = %s",
            (tier, user_id),
        )


def update_last_login(user_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = now(), updated_at = now() WHERE id = %s",
            (user_id,),
        )


# ---------------------------------------------------------------------------
# Refresh Token CRUD
# ---------------------------------------------------------------------------

def hash_token(token: str) -> str:
    """SHA-256 hash — only the hash is stored in DB, never plaintext."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token(
    user_id: int,
    family: str,
    expires_at,
    user_agent: str = "",
    ip_address: str = "",
) -> str:
    """Generate cryptographically secure opaque refresh token, store its hash."""
    raw_token = secrets.token_hex(48)  # 384 bits of entropy
    token_hash = hash_token(raw_token)
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO refresh_tokens
                (user_id, token_hash, family, expires_at, user_agent, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, token_hash, family, expires_at, user_agent, ip_address),
        )
    return raw_token


def get_refresh_token(raw_token: str) -> Optional[Dict[str, Any]]:
    token_hash = hash_token(raw_token)
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, family, is_revoked, expires_at, created_at
            FROM refresh_tokens WHERE token_hash = %s
            """,
            (token_hash,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "family": row[2],
            "is_revoked": row[3],
            "expires_at": row[4],
            "created_at": row[5],
            "token_hash": token_hash,
        }


def revoke_refresh_token(raw_token: str) -> None:
    token_hash = hash_token(raw_token)
    with _conn() as conn:
        conn.execute(
            "UPDATE refresh_tokens SET is_revoked = TRUE WHERE token_hash = %s",
            (token_hash,),
        )


def revoke_all_user_refresh_tokens(user_id: int) -> None:
    """Revoke all active tokens (logout-all / security incident response)."""
    with _conn() as conn:
        conn.execute(
            "UPDATE refresh_tokens SET is_revoked = TRUE WHERE user_id = %s AND is_revoked = FALSE",
            (user_id,),
        )


def revoke_token_family(family: str) -> None:
    """Detect token reuse (theft) — revoke the entire family immediately."""
    with _conn() as conn:
        conn.execute(
            "UPDATE refresh_tokens SET is_revoked = TRUE WHERE family = %s",
            (family,),
        )


def delete_expired_refresh_tokens() -> None:
    """Housekeeping — call periodically or via cron."""
    with _conn() as conn:
        conn.execute("DELETE FROM refresh_tokens WHERE expires_at < now()")


# ---------------------------------------------------------------------------
# Daily Usage Quota
# ---------------------------------------------------------------------------

def get_daily_usage(user_id: int) -> Dict[str, int]:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT posts_generated, images_generated
            FROM user_daily_usage
            WHERE user_id = %s AND usage_date = CURRENT_DATE
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return {"posts_generated": 0, "images_generated": 0}
        return {"posts_generated": row[0], "images_generated": row[1]}


def increment_daily_posts(user_id: int, count: int = 1) -> Dict[str, int]:
    with _conn() as conn:
        row = conn.execute(
            """
            INSERT INTO user_daily_usage (user_id, usage_date, posts_generated)
            VALUES (%s, CURRENT_DATE, %s)
            ON CONFLICT (user_id, usage_date)
            DO UPDATE SET posts_generated = user_daily_usage.posts_generated + EXCLUDED.posts_generated
            RETURNING posts_generated, images_generated
            """,
            (user_id, count),
        ).fetchone()
        return {"posts_generated": row[0], "images_generated": row[1]}


def increment_daily_images(user_id: int, count: int = 1) -> Dict[str, int]:
    with _conn() as conn:
        row = conn.execute(
            """
            INSERT INTO user_daily_usage (user_id, usage_date, images_generated)
            VALUES (%s, CURRENT_DATE, %s)
            ON CONFLICT (user_id, usage_date)
            DO UPDATE SET images_generated = user_daily_usage.images_generated + EXCLUDED.images_generated
            RETURNING posts_generated, images_generated
            """,
            (user_id, count),
        ).fetchone()
        return {"posts_generated": row[0], "images_generated": row[1]}


# ---------------------------------------------------------------------------
# Chat Sessions CRUD
# ---------------------------------------------------------------------------

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
            FROM chat_sessions WHERE user_id = %s
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


# ---------------------------------------------------------------------------
# Visual Profiles CRUD
# ---------------------------------------------------------------------------

def ensure_default_visual_profile(conn=None) -> None:
    seed_sql = """
    INSERT INTO visual_profiles (
        id, user_id, name, description, color_palette, typography_style,
        visual_mood, default_layout, platform_overrides, is_default, created_at, updated_at
    ) VALUES (
        'default-trendforge-profile', NULL, 'TrendForge Standard',
        'Default informative & clean visual identity',
        '{"primary": "#3B82F6", "secondary": "#10B981", "accent": "#F59E0B", "background": "#0F172A", "text": "#FFFFFF"}'::jsonb,
        'minimal-sans', 'clean-informative', 'minimal_clean', '{}'::jsonb, TRUE, now(), now()
    )
    ON CONFLICT (id) DO NOTHING;
    """
    if conn:
        conn.execute(seed_sql)
    else:
        with _conn() as c:
            c.execute(seed_sql)


def _profile_row(r) -> Dict[str, Any]:
    return {
        "id": r[0], "user_id": r[1], "name": r[2], "description": r[3],
        "color_palette": r[4], "typography_style": r[5], "visual_mood": r[6],
        "default_layout": r[7], "platform_overrides": r[8], "is_default": r[9],
        "created_at": r[10].isoformat() if r[10] else None,
        "updated_at": r[11].isoformat() if r[11] else None,
    }


def create_visual_profile_in_db(profile_data: Dict[str, Any]) -> str:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO visual_profiles (
                id, user_id, name, description, color_palette, typography_style,
                visual_mood, default_layout, platform_overrides, is_default, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name, description = EXCLUDED.description,
                color_palette = EXCLUDED.color_palette, typography_style = EXCLUDED.typography_style,
                visual_mood = EXCLUDED.visual_mood, default_layout = EXCLUDED.default_layout,
                platform_overrides = EXCLUDED.platform_overrides, is_default = EXCLUDED.is_default,
                updated_at = now()
            """,
            (
                profile_data["id"], profile_data.get("user_id"), profile_data["name"],
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
        return _profile_row(row) if row else None


def list_visual_profiles_from_db(user_id: int) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, name, description, color_palette, typography_style,
                   visual_mood, default_layout, platform_overrides, is_default, created_at, updated_at
            FROM visual_profiles WHERE user_id = %s OR is_default = TRUE
            ORDER BY is_default DESC, created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [_profile_row(r) for r in rows]


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
        res = conn.execute(
            f"UPDATE visual_profiles SET {', '.join(set_clauses)} WHERE id = %s",
            tuple(values),
        )
        return res.rowcount > 0


def delete_visual_profile_from_db(profile_id: str) -> bool:
    with _conn() as conn:
        res = conn.execute("DELETE FROM visual_profiles WHERE id = %s", (profile_id,))
        return res.rowcount > 0


# ---------------------------------------------------------------------------
# Image Assets CRUD
# ---------------------------------------------------------------------------

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
                asset_data["id"], asset_data.get("user_id"), asset_data.get("session_id", ""),
                asset_data.get("post_number", 1), asset_data.get("mode", "text_to_image"),
                asset_data.get("prompt", ""), asset_data.get("negative_prompt", ""),
                profile_id,
                Json(asset_data.get("visual_brief") or {}) if asset_data.get("visual_brief") else None,
                asset_data.get("provider_name", "mock"), asset_data.get("model_name", ""),
                Json(asset_data.get("generation_params") or {}),
                Json(asset_data.get("provider_metadata") or {}),
                asset_data.get("reference_asset_id"), asset_data.get("source_post_version", 1),
                asset_data.get("storage_backend", "local"), asset_data.get("storage_key", ""),
                asset_data.get("content_type", "image/png"), asset_data.get("file_size_bytes"),
                asset_data.get("status", "pending"), asset_data.get("error_message"),
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
            "id": row[0], "user_id": row[1], "session_id": row[2], "post_number": row[3],
            "mode": row[4], "prompt": row[5], "negative_prompt": row[6],
            "visual_profile_id": row[7], "visual_brief": row[8], "provider_name": row[9],
            "model_name": row[10], "generation_params": row[11], "provider_metadata": row[12],
            "reference_asset_id": row[13], "source_post_version": row[14],
            "storage_backend": row[15], "storage_key": row[16], "content_type": row[17],
            "file_size_bytes": row[18], "status": row[19], "error_message": row[20],
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
        res = conn.execute(
            f"UPDATE image_assets SET {', '.join(set_clauses)} WHERE id = %s",
            tuple(values),
        )
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
            FROM image_assets WHERE session_id = %s
            ORDER BY post_number ASC, created_at DESC
            """,
            (session_id,),
        ).fetchall()
        return [
            {
                "id": r[0], "user_id": r[1], "session_id": r[2], "post_number": r[3],
                "mode": r[4], "prompt": r[5], "visual_profile_id": r[6],
                "provider_name": r[7], "model_name": r[8], "reference_asset_id": r[9],
                "source_post_version": r[10], "storage_backend": r[11], "storage_key": r[12],
                "content_type": r[13], "file_size_bytes": r[14], "status": r[15],
                "error_message": r[16],
                "created_at": r[17].isoformat() if r[17] else None,
                "updated_at": r[18].isoformat() if r[18] else None,
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# User Preferences CRUD
# ---------------------------------------------------------------------------

def _default_preferences() -> Dict[str, Any]:
    return {
        "brand_name": "", "brand_handle": "@aiflick", "target_audience": "",
        "tone_of_voice": "punchy, authoritative, high-conversion",
        "custom_rules": "", "show_watermark": True, "preferred_model_tier": "free",
    }


def get_user_preferences(user_id: int) -> Dict[str, Any]:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT brand_name, brand_handle, target_audience, tone_of_voice,
                   custom_rules, show_watermark, preferred_model_tier
            FROM user_preferences WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return _default_preferences()
        return {
            "brand_name": row[0] or "", "brand_handle": row[1] or "@aiflick",
            "target_audience": row[2] or "",
            "tone_of_voice": row[3] or "punchy, authoritative, high-conversion",
            "custom_rules": row[4] or "", "show_watermark": bool(row[5]),
            "preferred_model_tier": row[6] or "free",
        }


def save_user_preferences(user_id: int, prefs: Dict[str, Any]) -> Dict[str, Any]:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id, brand_name, brand_handle, target_audience,
                tone_of_voice, custom_rules, show_watermark, preferred_model_tier, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (user_id) DO UPDATE SET
                brand_name = EXCLUDED.brand_name, brand_handle = EXCLUDED.brand_handle,
                target_audience = EXCLUDED.target_audience, tone_of_voice = EXCLUDED.tone_of_voice,
                custom_rules = EXCLUDED.custom_rules, show_watermark = EXCLUDED.show_watermark,
                preferred_model_tier = EXCLUDED.preferred_model_tier, updated_at = now()
            """,
            (
                user_id,
                prefs.get("brand_name", ""), prefs.get("brand_handle", "@aiflick"),
                prefs.get("target_audience", ""),
                prefs.get("tone_of_voice", "punchy, authoritative, high-conversion"),
                prefs.get("custom_rules", ""), prefs.get("show_watermark", True),
                prefs.get("preferred_model_tier", "free"),
            ),
        )
        return get_user_preferences(user_id)


# ---------------------------------------------------------------------------
# User Uploaded Assets CRUD
# ---------------------------------------------------------------------------

def create_user_uploaded_asset(
    asset_id: str,
    user_id: int,
    filename: str,
    mime_type: str,
    file_size_bytes: int,
    asset_role: str = "avatar",
    default_scope: str = "all",
    storage_key: str = "",
) -> Dict[str, Any]:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO user_uploaded_assets
                (id, user_id, filename, mime_type, file_size_bytes, asset_role, default_scope, storage_key, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
            """,
            (asset_id, user_id, filename, mime_type, file_size_bytes, asset_role, default_scope, storage_key),
        )
    return get_user_uploaded_asset(asset_id) or {}


def get_user_uploaded_asset(asset_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, filename, mime_type, file_size_bytes, asset_role, default_scope, storage_key, created_at
            FROM user_uploaded_assets WHERE id = %s
            """,
            (asset_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "filename": row[2],
            "mime_type": row[3],
            "file_size_bytes": row[4],
            "asset_role": row[5],
            "default_scope": row[6],
            "storage_key": row[7],
            "created_at": row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8]),
        }


def list_user_uploaded_assets(user_id: int) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, filename, mime_type, file_size_bytes, asset_role, default_scope, storage_key, created_at
            FROM user_uploaded_assets WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "user_id": r[1],
                "filename": r[2],
                "mime_type": r[3],
                "file_size_bytes": r[4],
                "asset_role": r[5],
                "default_scope": r[6],
                "storage_key": r[7],
                "created_at": r[8].isoformat() if hasattr(r[8], "isoformat") else str(r[8]),
            }
            for r in rows
        ]


def delete_user_uploaded_asset(asset_id: str, user_id: int) -> bool:
    with _conn() as conn:
        res = conn.execute(
            "DELETE FROM user_uploaded_assets WHERE id = %s AND user_id = %s",
            (asset_id, user_id),
        )
        return res.rowcount > 0

