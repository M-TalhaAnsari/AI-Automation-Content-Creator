"""
generation/content_generator.py — Step 5: Content Generator
(patched: see FIX comments for exactly what changed and why)
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
    def __init__(self):
        self._gemini_client = None

    def _get_gemini_client(self):
        if self._gemini_client is None:
            from google import genai
            self._gemini_client = genai.Client(api_key=CONFIG.models.gemini_api_key)
        return self._gemini_client

    _SELECTION_SCHEMA = {
        "type": "json_schema",
        "json_schema": {
            "name": "item_selection",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "selected_indices": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["selected_indices"],
                "additionalProperties": False,
            },
        },
    }

    def _call_groq_fallback(self, prompt: str, system_message: str = SYSTEM_PROMPT,
                             state: TrendForgeState = None, response_format=None) -> str:
        """Isolated helper to hit the Groq fallback endpoint cleanly.

        FIX (v2): response_format is now an explicit dict, not a bool.
        The original bug was forcing {"type": "json_object"} on a caller
        that wanted a bare array -- an object-mode guarantee can never be
        satisfied by an array, which is why Pass 1 failed on literally
        every call. The v1 fix just dropped enforcement for that caller,
        which stopped the failure but downgraded it to best-effort text +
        regex -- exactly the fragility this project has been moving away
        from everywhere else (see gate.py's strict-schema rewrite). This
        version instead wraps the array in a trivial object
        ({"selected_indices": [...]}) so Pass 1 gets the SAME strict,
        guaranteed-schema-conformant enforcement as everything else,
        rather than a weaker fallback. Defaults to the plain json_object
        object-mode used by the main generation path, unchanged.
        """
        from groq import Groq
        groq_client = Groq(api_key=CONFIG.models.groq_api_key)

        model_name = getattr(CONFIG.models, "groq_model_large", "llama-3.3-70b-versatile")
        if state is not None:
            add_log(state, f"[GroqFallback] Calling Groq with model={model_name}")

        kwargs = dict(
            model=model_name,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            reasoning_effort="low",
        )
        if response_format is None:
            response_format = {"type": "json_object"}
        if response_format:
            kwargs["response_format"] = response_format

        completion = groq_client.chat.completions.create(**kwargs)
        return completion.choices[0].message.content

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
                raw = self._call_groq_fallback(
                    prompt, system_message="Return ONLY a JSON object matching the requested schema.",
                    state=state, response_format=self._SELECTION_SCHEMA,
                )
            except Exception as groq_err:
                add_log(state, f"[Generator] Pass 1 Fallback failed: {groq_err} — Defaulting to top entries.")

        if raw:
            try:
                parsed = _parse_json(raw)
                indices = parsed.get("selected_indices", [])
                if indices:
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

        prompt = build_generation_prompt(state)
        raw_response = None
        tokens_used = 0
        engine_used = "None"

        try:
            add_log(state, f"[ContentGenerator] Sending generation instruction to {CONFIG.models.gemini_model}...")
            client = self._get_gemini_client()
            from google.genai import types

            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
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
                    state=state,
                    # use_json_object left at default True -- this call
                    # genuinely wants an object, unchanged from before.
                )
                engine_used = "Groq-LLaMA3"
                tokens_used = len(prompt.split()) + len(raw_response.split())
            except Exception as groq_error:
                add_error(state, f"[ContentGenerator] Critical: Fallback engine failed: {groq_error}")

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
        state["trend_insight"] = result.get("trend_insight", "")
        state["content_generation_engine"] = engine_used

        add_log(state, f"[ContentGenerator] Execution ended. Generated {len(validated)} posts via {engine_used}.")
        return state