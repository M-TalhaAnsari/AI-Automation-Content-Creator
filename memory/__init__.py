# memory package
"""
memory/ -- Public interface
===================================
Two separate stores with different lifetimes and purposes.

Usage:
    from memory import load_conversation, save_conversation, delete_conversation
    from memory import save_session, get_already_covered

What lives here:
    redis_session_store.py -- Active conversation state (Redis + Postgres fallback, Phase 7)
                             Keyed by (client_name, session_id). TTL-based sliding expiry.
    session_store.py       -- Permanent cross-session history (JSON file).
                             Used for dedup ("already covered") and analytics.
"""
from memory.redis_session_store import (
    load_conversation,
    save_conversation,
    delete_conversation,
    ping,
)
from memory.session_store import save_session, get_already_covered, get_history