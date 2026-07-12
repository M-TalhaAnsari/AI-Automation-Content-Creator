"""
generation/formatter.py — Final Output Formatter

Turns generated_posts list into a clean formatted string.
Also generates the token report.
Saves output to file.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import TrendForgeState, add_log
from core.token_tracker import TokenTracker
from config import CONFIG


def format_output(state: TrendForgeState) -> TrendForgeState:
    """Builds final_output string from generated_posts."""
    posts = state.get("generated_posts", [])
    platform = state.get("platform", "instagram").upper()
    topic = state.get("core_topic", "")
    # sources_used always exists (create_initial_state sets it to []), so
    # no fallback key is needed here — selected_sources is a different,
    # intentionally distinct field (what the router picked vs what actually
    # returned data).
    sources = state.get("sources_used", [])
    trend_insight = state.get("trend_insight", "")

    lines = []
    lines.append(f"\n{'╔' + '═'*58 + '╗'}")
    lines.append(f"║  🔥 TRENDFORGE — {platform} CONTENT SERIES{' '*(38-len(platform))}║")
    lines.append(f"║  Topic: {topic[:48]}{' '*(49-min(len(topic),48))}║")
    lines.append(f"║  Sources: {', '.join(sources)[:46]}{' '*(47-min(len(', '.join(sources)),46))}║")
    lines.append(f"{'╚' + '═'*58 + '╝'}\n")

    if not posts:
        lines.append("  ⚠️  No posts generated. Check your API keys and fetched data.")
        state["final_output"] = "\n".join(lines)
        return state

    for post in posts:
        n = post.get("number", "?")
        title = post.get("title", "")
        hook = post.get("hook", "")
        summary = post.get("summary", [])
        link = post.get("link", "")
        caption = post.get("caption", "")
        hashtags = " ".join(post.get("hashtags", []))

        lines.append(f"{'─'*60}")
        lines.append(f"  POST {n}/{len(posts)} — {title}")
        lines.append(f"{'─'*60}")
        lines.append(f"\n  🔥 HOOK")
        lines.append(f"  {hook}")
        lines.append(f"\n  📌 SUMMARY")
        for bullet in summary:
            lines.append(f"  {bullet}")
        if link:
            lines.append(f"\n  🔗 LINK")
            lines.append(f"  {link}")
        lines.append(f"\n  ✍️  CAPTION")
        for cap_line in caption.split("\n"):
            lines.append(f"  {cap_line}")
        lines.append(f"\n  🏷️  HASHTAGS")
        lines.append(f"  {hashtags}")
        lines.append("")

    # Trend insight
    if trend_insight:
        lines.append(f"{'─'*60}")
        lines.append(f"  📊 TREND INSIGHT")
        lines.append(f"{'─'*60}")
        lines.append(f"  {trend_insight}\n")

    # Token report — label the content-generation engine dynamically based
    # on which one actually ran this session (see content_generator.py),
    # instead of a hardcoded name that drifts when models/configs change.
    gen_engine = state.get("content_generation_engine", "")
    if "groq" in gen_engine.lower():
        gen_model_label = f"{CONFIG.models.groq_model_large} (Groq)"
    else:
        gen_model_label = CONFIG.models.gemini_model
    models_used = [f"{CONFIG.models.groq_model_small} (Groq)", gen_model_label]

    tracker = TokenTracker(state)
    lines.append(tracker.generate_report(
        sources_used=sources,
        models_used=models_used
    ))

    state["final_output"] = "\n".join(lines)
    add_log(state, "[Formatter] Output formatted")
    return state


def save_output(state: TrendForgeState, output_dir: str = "output") -> str:
    """Saves final output to file. Returns file path (empty string on failure)."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        # Use .get() with a fallback so a missing/renamed session_id can
        # never crash the run at the very last step, after generation has
        # already succeeded and already cost tokens.
        session_id = state.get("session_id", "unknown")
        path = os.path.join(output_dir, f"session_{session_id}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(state.get("final_output", ""))
        add_log(state, f"[Formatter] Saved to {path}")
        return path
    except Exception as e:
        add_log(state, f"[Formatter] Save failed: {e}")
        return ""