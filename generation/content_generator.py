"""
generation/content_generator.py — Step 5: Content Generator

FIX (this session): routed through the LLM gateway (llm/client.py) per
ARCHITECTURE.md principle #3 -- "All LLM calls go through llm/client.py.
No other file imports groq or google.genai." This file used to
instantiate both SDKs directly and roll its own ad-hoc JSON parser
(_parse_json, with regex trailing-comma repair) as a substitute for the
schema validation the gateway guarantees everywhere else. That parser
is gone; llm/client.py's model_validate_json() is now the only path.

KNOWN, DELIBERATE BEHAVIOR CHANGE from this fix: llm/client.py's
contract is "hard error on schema violation, no prose-repair cascades"
(see that module's docstring), and llm/schemas.py's GeneratedPostsSchema
validates the WHOLE posts array in one call (including the "^#" hashtag
pattern PostItem.hashtags enforces). Before this fix, a single malformed
post in an otherwise-good batch could be silently dropped while the rest
shipped. Now one bad post anywhere in the batch fails validation for the
ENTIRE call, which triggers the Groq fallback, and if that also fails,
_build_fallback_posts() (the template safety net) takes over -- same
end state as before, just triggered by one stricter condition instead
of a per-post filter. This is a direct, load-bearing consequence of the
gateway's existing hard-error contract, not a new policy invented here.

ALSO FIXED as a side effect: previously, if raw_response parsed but ALL
individual posts failed the old hook/caption check, engine_used stayed
labeled "Gemini" or "Groq-LLaMA3" even though the template fallback ran
-- formatter.py would then mislabel a total-failure run as a successful
LLM generation. Now engine_used is explicitly reset to "None" whenever
`validated` ends up empty, regardless of why.
"""

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


# Local to this file, deliberately NOT added to llm/schemas.py's central
# registry -- that module's docstring says "Deliberately NOT here: a
# SelectionSchema... don't rebuild it without a concrete regression-set
# reason." That note is about not resurrecting the old standalone
# SelectionAgent's formal schema after Agent 10 was merged into Agent 5.
# This is smaller: an internal implementation detail of THIS file's own
# Pass-1 "pick the best N of the fetched items" step, called from
# nowhere else. Kept local so that distinction stays visible.
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

        # NOTE: previously the Gemini branch of this call had NO
        # temperature set at all (provider default) while the Groq
        # fallback used 0.2 -- an inconsistency, and neither used any
        # named config value. routing_temperature (0.0) is used for
        # both here: this is a low-creativity, structural "pick indices"
        # decision, the same category ModelConfig defines that field for.
        result = None
        try:
            result = call_gemini(
                system="Return ONLY a JSON object matching the requested schema.",
                user=prompt,
                model=CONFIG.models.gemini_model,
                schema=_SelectionResult,
                temperature=CONFIG.models.routing_temperature,
            )
        except (LLMCallFailed, LLMSchemaViolation) as e:
            add_log(state, f"[Generator] Pass 1 Gemini failed ({e}). Trying Groq Fallback...")
            try:
                result = call_groq(
                    system="Return ONLY a JSON object matching the requested schema.",
                    user=prompt,
                    model=CONFIG.models.groq_model_large,
                    schema=_SelectionResult,
                    temperature=CONFIG.models.routing_temperature,
                    reasoning_effort="low",
                )
            except (LLMCallFailed, LLMSchemaViolation) as groq_err:
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
                temperature=CONFIG.models.generation_temperature,
            )
            engine_used = "Gemini"
        except (LLMCallFailed, LLMSchemaViolation) as gemini_error:
            add_error(state, f"[ContentGenerator] Gemini Service Alert: {gemini_error}")
            add_log(state, "[ContentGenerator] Rerouting operational prompt to Groq (LLaMA3) infrastructure...")
            try:
                result = call_groq(
                    system=SYSTEM_PROMPT,
                    user=prompt,
                    model=CONFIG.models.groq_model_large,
                    schema=GeneratedPostsSchema,
                    temperature=CONFIG.models.generation_temperature,
                    reasoning_effort="low",
                )
                engine_used = "Groq-LLaMA3"
            except (LLMCallFailed, LLMSchemaViolation) as groq_error:
                add_error(state, f"[ContentGenerator] Critical: Fallback engine failed: {groq_error}")

        validated = []
        if result is not None:
            add_log(state, f"[Generator] Raw payload validated successfully via {engine_used}.")
            add_tokens(state, "content_generation", result.tokens_used)
            # FIX: hashtag "#" normalization used to happen here by hand
            # (t if t.startswith("#") else f"#{t}"). PostItem.hashtags now
            # enforces the "^#" pattern as part of schema validation
            # itself -- a malformed hashtag is a hard LLMSchemaViolation
            # on the call above, not something silently patched after.
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