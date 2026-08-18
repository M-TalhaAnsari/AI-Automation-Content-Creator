import html
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import BaseModel

from core.state import TrendForgeState, add_log, add_error, add_tokens
from generation.prompt_composer import compose_prompt
from generation.prompts import SYSTEM_PROMPT
from Config.config import CONFIG
from llm.client import call_gemini, call_groq
from llm.errors import LLMCallFailed, LLMSchemaViolation
from llm.schemas import GeneratedPostsSchema


class _SelectionResult(BaseModel):
    selected_indices: list[int]


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

    def _select_best_items(self, state: TrendForgeState, all_items: list) -> list:
        count = state.get("post_count", 10)
        topic = state.get("core_topic", "")
        platform = state.get("platform", "Instagram")

        if len(all_items) <= count:
            return all_items

        items_text = "\n".join(
            f"{i+1}. {item.get('title','')}: {str(item.get('description', item.get('summary', item.get('snippet',''))))[:120]}"
            for i, item in enumerate(all_items[:20])
        )

        prompt = f"""Topic: "{topic}"
Items:
{items_text}

Pick the {count} most interesting, engaging, and relevant items for building an authority presence on {platform}.
Return this exact JSON object: {{"selected_indices": [<1-based integers, {count} of them>]}}"""

        result = None
        try:
            result = call_gemini(
                system="Return ONLY a JSON object matching the requested schema.",
                user=prompt,
                model=CONFIG.models.gemini_model,
                schema=_SelectionResult,
                temperature=0.2,
            )
        except (LLMCallFailed, LLMSchemaViolation) as e:
            add_log(state, f"[Generator] Pass 1 Gemini failed ({e}). Trying Groq Fallback...")
            try:
                result = call_groq(
                    system="Return ONLY a JSON object matching the requested schema.",
                    user=prompt,
                    model=CONFIG.models.groq_model_large,
                    schema=_SelectionResult,
                    temperature=0.2,
                    reasoning_effort="low",
                )
            except (LLMCallFailed, LLMSchemaViolation) as groq_err:
                add_tokens(state, "content_generation", getattr(groq_err, "tokens_used", 0))
                add_log(state, f"[Generator] Pass 1 Fallback failed: {groq_err} — Defaulting to top entries.")

        if result is not None:
            add_tokens(state, "content_generation", result.tokens_used)
            indices = result.content.get("selected_indices", [])
            if indices:
                selected = []
                for idx in indices:
                    if 1 <= int(idx) <= len(all_items):
                        selected.append(all_items[int(idx) - 1])
                add_log(state, f"[Generator] Pass 1 selected indices: {indices}")
                if selected:
                    return selected[:count]
                add_log(state, "[Generator] Pass 1 indices were all out of range — falling back to top entries.")

        return all_items[:count]

    def generate(self, state: TrendForgeState) -> TrendForgeState:
        add_log(state, "[ContentGenerator] Starting generation cycle...")

        total_items = state.get("total_items_fetched", 0)
        fetched_data = state.get("fetched_data", {})
        add_log(state, f"[ContentGenerator] Processing {total_items} fetched items across {len(fetched_data)} sources")

        topic = state.get("core_topic", "")
        content_intent = state.get("content_intent", "showcase")

        if topic and content_intent != "educate":
            topic_words = [w.lower() for w in topic.split() if len(w) > 2]
            if topic_words:
                filtered = {}
                for source, items in fetched_data.items():
                    relevant = []
                    for item in items:
                        title = item.get("title", "").lower()
                        summary = item.get("summary", item.get("description", item.get("snippet", ""))).lower()
                        if any(word in title or word in summary for word in topic_words):
                            relevant.append(item)
                    if relevant:
                        filtered[source] = relevant
                state["fetched_data"] = filtered
                add_log(state, f"[ContentGenerator] Filtered down to {sum(len(v) for v in filtered.values())} relevant items")
        else:
            add_log(state, f"[ContentGenerator] Skipped topic filter — intent={content_intent}")

        all_items = []
        for source, items in state.get("fetched_data", {}).items():
            for item in items:
                item["_source"] = source
                all_items.append(item)

        target_count = state.get("post_count", 5)
        add_log(state, f"[ContentGenerator] Pre-selection state — total_items={len(all_items)}, target_count={target_count}, intent={content_intent}")

        if content_intent != "educate" and len(all_items) > target_count:
            add_log(state, f"[Generator] Pass 1 — Selecting best {target_count} from {len(all_items)} components")
            best_items = self._select_best_items(state, all_items)
            regrouped = {}
            for item in best_items:
                src = item.get("_source", "selected")
                regrouped.setdefault(src, []).append(item)
            state["fetched_data"] = regrouped

            selected_ids = {id(item) for item in best_items}
            state["leftover_fetch_pool"] = [item for item in all_items if id(item) not in selected_ids]
        else:
            add_log(state, f"[Generator] Skipped Pass 1 selection — intent={content_intent}, keeping all {len(all_items)} items as loose reference")
            state["leftover_fetch_pool"] = []

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