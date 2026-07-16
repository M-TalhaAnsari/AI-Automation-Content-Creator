"""
generation/content_generator.py — Step 5: Content Generator

Uses Gemini 2.0 Flash to turn real fetched data into
platform-ready posts with hooks, summaries, captions, hashtags.

Why Gemini here (not Groq)?
- Gemini 2.0 Flash has superior creative writing quality
- Better at following complex structured output instructions
- 1M token context window — handles large fetched datasets
- Free tier: 1500 req/day
"""

import json
import re
import sys
import os
import html
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import TrendForgeState, add_log, add_error, add_tokens
from generation.prompts import build_generation_prompt, SYSTEM_PROMPT
from config import CONFIG


def _parse_json(text: str) -> dict:
    """Multi-strategy JSON parser — never crashes."""
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    try:
        s = text.index("{")
        e = text.rindex("}") + 1
        return json.loads(text[s:e])
    except Exception:
        pass
    try:
        fixed = re.sub(r',\s*([}\]])', r'\1', text)
        s = fixed.index("{")
        e = fixed.rindex("}") + 1
        return json.loads(fixed[s:e])
    except Exception:
        pass
    return {}


def _build_fallback_posts(state: TrendForgeState) -> list:
    """
    If Gemini and Groq fail entirely, build basic posts from raw fetched data.
    Guarantees the pipeline always produces output.
    """
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
            url  = item.get("link", "")
            # Matches the same fallback chain used in prompts.py and the
            # topic filter below — previously only checked "summary", which
            # silently produced empty descriptions for fetchers that store
            # their text under "description" or "snippet" instead.
            desc = item.get("summary", item.get("description", item.get("snippet", "")))
            title = html.unescape(title).strip()
            desc  = html.unescape(str(desc)).strip()
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
    """
    Dual-engine Content Generator.
    Primary: Gemini 2.0 Flash
    Fallback: Groq LLaMA 3
    Reads fetched_data from state, writes generated_posts + final_output.
    """

    def __init__(self):
        self._gemini_client = None

    def _get_gemini_client(self):
        """Lazy Gemini client initialization."""
        if self._gemini_client is None:
            from google import genai
            self._gemini_client = genai.Client(api_key=CONFIG.models.gemini_api_key)
        return self._gemini_client

    def _call_groq_fallback(self, prompt: str, system_message: str = SYSTEM_PROMPT, state: TrendForgeState = None) -> str:
        """Isolated helper to hit the Groq fallback endpoint cleanly."""
        from groq import Groq
        groq_client = Groq(api_key=CONFIG.models.groq_api_key)

        # Uses whichever large Groq model is configured. Groq legitimately
        # hosts OpenAI's open-weight gpt-oss models, so an "openai/..."
        # prefix here is expected, not a stray invalid string — a previous
        # guard here swapped any "openai"/"gpt"-containing name to
        # llama-3.3-70b-versatile, which meant the actual API call used a
        # different model than the one the token report displayed.
        model_name = getattr(CONFIG.models, "groq_model_large", "llama-3.3-70b-versatile")
        if state is not None:
            add_log(state, f"[GroqFallback] Calling Groq with model={model_name}")

        completion = groq_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return completion.choices[0].message.content

    def _select_best_items(self, state: TrendForgeState, all_items: list) -> list:
        """Pass 1 — ask LLM to pick the best N items from noisy data."""
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
Return ONLY a JSON array of index numbers (1-based). Example: [1, 3, 5, 7, 9]"""

        raw = None
        try:
            client = self._get_gemini_client()
            response = client.models.generate_content(
                model=CONFIG.models.gemini_model,
                contents=prompt,
            )
            raw = response.text
        except Exception as e:
            add_log(state, f"[Generator] Pass 1 Gemini failed ({e}). Trying Groq Fallback...")
            try:
                raw = self._call_groq_fallback(prompt, system_message="Return ONLY a JSON array of integers.", state=state)
            except Exception as groq_err:
                add_log(state, f"[Generator] Pass 1 Fallback failed: {groq_err} — Defaulting to top entries.")

        if raw:
            try:
                match = re.search(r'\[.*?\]', raw, re.DOTALL)
                if match:
                    indices = json.loads(match.group())
                    selected = []
                    for idx in indices:
                        if 1 <= int(idx) <= len(all_items):
                            selected.append(all_items[int(idx) - 1])
                    add_log(state, f"[Generator] Pass 1 selected indices: {indices}")
                    return selected[:count]
            except Exception as parse_err:
                add_log(state, f"[Generator] Pass 1 failed to parse index JSON: {parse_err}")

        return all_items[:count]

    def generate(self, state: TrendForgeState) -> TrendForgeState:
        add_log(state, "[ContentGenerator] Starting generation cycle...")

        total_items = state.get("total_items_fetched", 0)
        fetched_data = state.get("fetched_data", {})
        add_log(state, f"[ContentGenerator] Processing {total_items} fetched items across {len(fetched_data)} sources")

        # ── FILTER RELEVANT DATA ──
        topic = state.get("core_topic", "")
        content_intent = state.get("content_intent", "showcase")

        if topic and content_intent != "educate":   # skip strict filter for educate — model uses own knowledge
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
                # NOTE: intentional narrowing — fetched_data is reassigned
                # again below (Pass 1 selection) if there are still more
                # items than post slots. This is a deliberate two-stage
                # funnel (filter -> select), not a silent override.
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
            # Regroup selected items back under their original source keys
            # (each item was tagged with item["_source"] above) instead of
            # collapsing everything into one "[SELECTED]" bucket — this
            # preserves the per-source provenance the prompt builder uses
            # (e.g. distinguishing GitHub star counts from a Tavily snippet).
            regrouped = {}
            for item in best_items:
                src = item.get("_source", "selected")
                regrouped.setdefault(src, []).append(item)
            state["fetched_data"] = regrouped

            # Phase 2: retain what Pass 1 didn't select. Previously this was
            # a local variable, discarded the moment generate() returned —
            # confirmed via grep before this fix, not assumed. targeted_refetch
            # (conversation/actions.py) needs this pool to check whether a
            # follow-up request ("broaden this", "not this one") can be
            # satisfied from data already paid to fetch, before triggering a
            # brand new network fetch.
            selected_ids = {id(item) for item in best_items}
            state["leftover_fetch_pool"] = [item for item in all_items if id(item) not in selected_ids]
        else:
            add_log(state, f"[Generator] Skipped Pass 1 selection — intent={content_intent}, keeping all {len(all_items)} items as loose reference")
            # Nothing was narrowed (educate mode, or fetched count already <=
            # target) — no leftover to speak of.
            state["leftover_fetch_pool"] = []

        prompt = build_generation_prompt(state)
        raw_response = None
        tokens_used = 0
        engine_used = "None"

        # ── EXECUTING CREATIVE GENERATION LOOP ──
        try:
            add_log(state, f"[ContentGenerator] Sending generation instruction to {CONFIG.models.gemini_model}...")
            client = self._get_gemini_client()
            from google.genai import types

            # Setup base configurations
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )

            # Only attach thinking config when an explicit reasoning model is configured
            if "thinking" in getattr(CONFIG.models, "gemini_model", "").lower():
                gen_config.thinking_config = types.ThinkingConfig(thinking_level="medium")

            response = client.models.generate_content(
                model=CONFIG.models.gemini_model,
                contents=prompt,
                config=gen_config
            )

            raw_response = response.text
            engine_used = "Gemini"

            try:
                tokens_used = response.usage_metadata.total_token_count
            except Exception:
                tokens_used = len(prompt.split()) + len(raw_response.split())

        except Exception as gemini_error:
            add_error(state, f"[ContentGenerator] Gemini Service Alert: {gemini_error}")
            add_log(state, "[ContentGenerator] Rerouting operational prompt to Groq (LLaMA3) infrastructure...")

            try:
                raw_response = self._call_groq_fallback(
                    prompt=prompt,
                    system_message="You are a senior social media copywriter. Output your final generation in strict, clean JSON matching the template format exactly.",
                    state=state
                )
                engine_used = "Groq-LLaMA3"
                tokens_used = len(prompt.split()) + len(raw_response.split())
            except Exception as groq_error:
                add_error(state, f"[ContentGenerator] Critical: Fallback engine failed: {groq_error}")

        # ── POST GENERATION TREATMENT ──
        result = {}
        if raw_response:
            add_log(state, f"[Generator] Raw payload fetched successfully via {engine_used}.")
            result = _parse_json(raw_response)
            add_tokens(state, "content_generation", tokens_used)

        posts = result.get("posts", [])
        validated = []

        for p in posts:
            if isinstance(p, dict) and p.get("hook") and p.get("caption"):
                tags = p.get("hashtags", [])
                p["hashtags"] = [(t if t.startswith("#") else f"#{t}") for t in tags]
                validated.append(p)
            else:
                add_log(state, f"[ContentGenerator] Dropped a post slot — missing hook and/or caption: {p if isinstance(p, dict) else type(p)}")

        if not validated:
            add_log(state, "[ContentGenerator] System Warning: Engine outputs empty or malformed — applying safe string builder.")
            validated = _build_fallback_posts(state)

        state["generated_posts"] = validated
        state["final_output"] = result.get("series_hook", "")
        # Own field, not a fallback onto fetch_summary — that field already
        # means "primary search query" (set in intent_extractor.py). Reusing
        # it here meant a missing trend_insight in the model's response
        # silently displayed the search query as if it were an insight.
        state["trend_insight"] = result.get("trend_insight", "")
        # Record which engine actually served this run so token_tracker.py
        # and formatter.py can price/label it correctly instead of always
        # assuming Gemini — content_generation tokens can come from either
        # engine depending on the fallback path taken above.
        state["content_generation_engine"] = engine_used

        add_log(state, f"[ContentGenerator] Execution ended. Generated {len(validated)} posts via {engine_used}.")
        return state