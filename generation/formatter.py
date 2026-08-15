"""
generation/formatter.py — Final Output Formatter
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import TrendForgeState, add_log
from core.token_tracker import TokenTracker
from Config.config import CONFIG


def format_output(state: TrendForgeState) -> TrendForgeState:
    posts = state.get("generated_posts", [])
    platform = state.get("platform", "instagram").upper()
    topic = state.get("core_topic", "")
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

    if trend_insight:
        lines.append(f"{'─'*60}")
        lines.append(f"  📊 TREND INSIGHT")
        lines.append(f"{'─'*60}")
        lines.append(f"  {trend_insight}\n")

    # FIX: gen_engine == "None" (both providers failed schema validation,
    # _build_fallback_posts() ran) used to fall into the `else` branch
    # below and get mislabeled as CONFIG.models.gemini_model -- claiming
    # a successful Gemini generation for a total-failure/template run.
    gen_engine = state.get("content_generation_engine", "")
    gen_engine_lower = gen_engine.lower()
    if not gen_engine or gen_engine_lower == "none":
        gen_model_label = "Template fallback (no LLM — both providers failed validation)"
    elif "groq" in gen_engine_lower:
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
    try:
        os.makedirs(output_dir, exist_ok=True)
        session_id = state.get("session_id", "unknown")
        path = os.path.join(output_dir, f"session_{session_id}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(state.get("final_output", ""))
        add_log(state, f"[Formatter] Saved to {path}")
        return path
    except Exception as e:
        add_log(state, f"[Formatter] Save failed: {e}")
        return ""