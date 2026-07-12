"""
memory/session_store.py — Session Memory Store
Saves every run to JSON for history and future reference.
"""

import json, os, sys
from datetime import datetime, timedelta
from typing import List, Dict
from core.state import TrendForgeState, get_total_tokens


MEMORY_PATH = "memory/sessions.json"


def _load(path: str) -> Dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            # Previously this silently discarded a corrupted/unreadable
            # history file and returned an empty one with no indication
            # anywhere that history had just been reset. Surface it instead.
            print(f"[SessionStore] Warning: could not read {path} ({e}) — "
                  f"starting with empty history. The existing file was left untouched.",
                  file=sys.stderr)
    return {"sessions": []}


def save_session(state: TrendForgeState, path: str = MEMORY_PATH):
    data = _load(path)
    data["sessions"].append({
        "session_id":   state["session_id"],
        "timestamp":    datetime.utcnow().isoformat(),
        "prompt":       state["raw_prompt"],
        "topic":        state["core_topic"],
        "platform":     state["platform"],
        "sources_used": state.get("sources_used", []),
        "posts_count":  len(state.get("generated_posts", [])),
        # Use the single canonical total-tokens computation (core/state.py)
        # instead of recomputing the sum here — avoids a second source of
        # truth that could silently drift if the tokens dict shape changes.
        "total_tokens": get_total_tokens(state),
        "errors":       state["errors"],
        # Minimal per-post signature (not the full caption/hashtags — just
        # enough to detect repeats). Capped at 10 to keep the history file
        # small; posts_count above still reflects the true total.
        "posts": [
            {"title": p.get("title", ""), "link": p.get("link", "")}
            for p in state.get("generated_posts", [])
        ][:10],
    })
    # Keep last 100 sessions
    data["sessions"] = data["sessions"][-100:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_history(limit: int = 10, path: str = MEMORY_PATH) -> List[Dict]:
    return _load(path)["sessions"][-limit:]


def get_already_covered(
    topic: str,
    platform: str,
    max_age_days: int = 30,
    limit: int = 15,
    path: str = MEMORY_PATH,
) -> List[Dict]:
    """
    Returns previously-generated post titles/links for the same topic and
    platform, within a recency window, so a new run can be told to avoid
    repeating them.

    Matching is intentionally lenient (case-insensitive substring, either
    direction) since the same subject is often phrased slightly differently
    across runs — e.g. "docker" vs "docker containers". This is a known
    limitation, not exhaustive topic-similarity matching; it will miss
    genuinely different phrasings of the same subject and will over-match
    on short, generic topic words. Revisit if that turns out to matter in
    real use.

    max_age_days prevents an old session from suppressing fresh content
    indefinitely — without this, a topic covered once months ago would
    silently narrow every future run on that topic forever.
    """
    sessions = _load(path)["sessions"]
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    topic_l = (topic or "").lower().strip()
    if not topic_l:
        return []

    seen: List[Dict] = []
    seen_keys = set()

    for s in reversed(sessions):  # most recent first
        try:
            ts = datetime.fromisoformat(s["timestamp"])
        except Exception:
            continue
        if ts < cutoff:
            continue
        if s.get("platform") != platform:
            continue
        s_topic = (s.get("topic") or "").lower().strip()
        if not s_topic:
            continue
        if topic_l not in s_topic and s_topic not in topic_l:
            continue

        for p in s.get("posts", []):
            title = p.get("title", "")
            if not title:
                continue
            key = (title, p.get("link", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            seen.append({"title": title, "link": p.get("link", "")})
            if len(seen) >= limit:
                return seen

    return seen