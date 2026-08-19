import html
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import TrendForgeState, add_log, add_error, add_tokens
from generation.prompt_composer import compose_prompt
from generation.prompts import SYSTEM_PROMPT
from Config.config import CONFIG
from llm.client import call_gemini, call_groq
from llm.errors import LLMCallFailed, LLMSchemaViolation
from llm.schemas import GeneratedPostsSchema


def _build_fallback_posts(state: TrendForgeState) -> list:
    posts = []
    fetched = state.get("fetched_data", {})
    topic = state.get("core_topic", "trending topics")
    count = state.get("post_count", 5)
    n = 0

    for source, items in fetched.items():
        for item in items:
            if n >= count:
                break
            title = item.get("title", item.get("name", f"Item {n+1}"))
            url = item.get("link", "")
            desc = item.get("summary", item.get("description", item.get("snippet", "")))
            title = html.unescape(title).strip()
            desc = html.unescape(str(desc)).strip()
            posts.append({
                "number": n + 1,
                "title": title,
                "hook": f"This {topic} project is changing everything 👇",
                "summary": [
                    f"📌 {str(desc)[:80]}" if desc else f"📌 {title}",
                    "🔗 Check the link for full details",
                    "⭐ Save this post to revisit later",
                ],
                "link": url,
                "caption": f"🚀 {title}\n\n{str(desc)[:150]}\n\nLink in bio 👆\n\nSave this! 🔖",
                "hashtags": [f"#{topic.replace(' ', '')}", "#trending", "#fyp", "#viral", "#learnmore"],
            })
            n += 1
        if n >= count:
            break

    return posts


class ContentGenerator:

    def generate(self, state: TrendForgeState) -> TrendForgeState:
        add_log(state, "[ContentGenerator] Starting generation cycle...")

        total_items = state.get("total_items_fetched", 0)
        fetched_data = state.get("fetched_data", {})
        add_log(state, f"[ContentGenerator] Processing {total_items} fetched items across {len(fetched_data)} sources")

        topic = state.get("core_topic", "")
        content_intent = state.get("content_intent", "showcase")

        all_items = []
        for source, items in state.get("fetched_data", {}).items():
            for item in items:
                item["_source"] = source
                all_items.append(item)

        target_count = state.get("post_count", 5)
        add_log(state, f"[ContentGenerator] Single-pass curation & generation — total_items={len(all_items)}, target_count={target_count}, intent={content_intent}")

        # Retain full pool in state for conversational refetch / add operations
        state["leftover_fetch_pool"] = list(all_items)

        prompt = compose_prompt(state)

        result = None
        engine_used = "None"

        try:
            add_log(state, f"[ContentGenerator] Sending generation instruction to {CONFIG.models.gemini_model}...")
            result = call_gemini(
                system=SYSTEM_PROMPT,
                user=prompt,
                model=CONFIG.models.gemini_model,
                schema=GeneratedPostsSchema,
                temperature=0.2,
            )
            engine_used = "Gemini"
        except (LLMCallFailed, LLMSchemaViolation) as gemini_error:
            add_tokens(state, "content_generation", getattr(gemini_error, "tokens_used", 0))
            add_error(state, f"[ContentGenerator] Gemini Service Alert: {gemini_error}")
            add_log(state, "[ContentGenerator] Rerouting operational prompt to Groq (LLaMA3) infrastructure...")
            try:
                result = call_groq(
                    system=SYSTEM_PROMPT,
                    user=prompt,
                    model=CONFIG.models.groq_model_large,
                    schema=GeneratedPostsSchema,
                    temperature=0.2,
                    reasoning_effort="low",
                )
                engine_used = "Groq-LLaMA3"
            except (LLMCallFailed, LLMSchemaViolation) as groq_error:
                add_tokens(state, "content_generation", getattr(groq_error, "tokens_used", 0))
                add_error(state, f"[ContentGenerator] Critical: Fallback engine failed: {groq_error}")

        validated = []
        if result is not None:
            add_log(state, f"[Generator] Raw payload validated successfully via {engine_used}.")
            add_tokens(state, "content_generation", result.tokens_used)
            validated = result.content.get("posts", [])

        if not validated:
            add_log(state, "[ContentGenerator] System Warning: Engine output empty or failed validation — applying safe string builder.")
            validated = _build_fallback_posts(state)
            engine_used = "None"

        state["generated_posts"] = validated
        state["final_output"] = result.content.get("series_hook", "") if result else ""
        state["trend_insight"] = result.content.get("trend_insight", "") if result else ""
        state["content_generation_engine"] = engine_used

        add_log(state, f"[ContentGenerator] Execution ended. Generated {len(validated)} posts via {engine_used}.")
        return state