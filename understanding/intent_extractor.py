"""
understanding/intent_extractor.py — LLM-Powered Intent Extractor
(patched: see FIX comment for exactly what changed and why)
"""

import json
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CONFIG, SUPPORTED_PLATFORMS
from core.state import TrendForgeState, add_log, add_error, add_tokens


TOPIC_FILLER_PATTERN = (
    r'\b(any|some|top|best|latest|new|give me|i want|i need|for my|please|'
    r'can you|could you|help me|create|make|build|generate|instagram|'
    r'youtube|tiktok|linkedin|post|content|news about|topic|related to|'
    r'that i|that make|for)\b'
)

TRAILING_WORD_PATTERN = r'\s+(to|and|or|the|a|an|with|by|in|on|at)$'


def _strip_topic_filler(text: str) -> str:
    cleaned = re.sub(TOPIC_FILLER_PATTERN, '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(TRAILING_WORD_PATTERN, '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned


CATEGORY_DEFAULT_INTENT = {
    "tech":           "showcase",
    "business":       "news",
    "lifestyle":      "inspire",
    "entertainment":  "review",
    "education":      "educate",
    "news":           "news",
    "unknown":        "showcase",
}


INTENT_SYSTEM_PROMPT = """You are a precise intent extraction engine for a social media content system.

Your job: understand what the user ACTUALLY wants to post about and extract clean structured intent.

CRITICAL INSTRUCTIONS FOR `post_count`:
- This refers to the number of distinct items (posts/projects/slides) to create.
- Default to 5.
- IGNORE numbers that refer to formatting (e.g., '1 line', '2 sentences', '3 words', '4 paragraphs').
- If the user says "give me 3 projects, each in 1 sentence", the post_count is 3, NOT 1.

Critical rules:
- core_topic must be the SUBJECT ONLY — never include "I want", "give me", "latest news about", "for instagram"
- category must be decisive — never return unknown for clear topics
- search_query must be specific enough to find exactly what's needed
- Return ONLY valid JSON, nothing else""".strip()


def _build_intent_prompt(cleaned_text: str, pre_extracted: dict) -> str:
    already_known = []
    if pre_extracted.get("detected_platform"):
        already_known.append(f'platform="{pre_extracted["detected_platform"]}"')
    if pre_extracted.get("detected_post_count"):
        already_known.append(f'post_count={pre_extracted["detected_post_count"]}')
    if pre_extracted.get("detected_special_requests"):
        already_known.append(f'special_requests={pre_extracted["detected_special_requests"]}')
    known_str = f"\nAlready known: {'; '.join(already_known)}" if already_known else ""

    return f"""You are an expert content intent classifier. Extract precise intent from user prompts.

RULES:
1. core_topic: Extract ONLY the actual subject. Remove all meta-words like "I want", "give me", "top", "best", "latest", "news about", "for my instagram", "that make user".
   Examples:
   - "I want top 5 ML projects for instagram" → "machine learning projects"
   - "what is the latest news about claude fable 5" → "claude fable 5"
   - "get me trending content about discipline motivation" → "discipline motivation"
   - "best python libraries for beginners" → "python libraries beginners"

2. category: Be decisive, never return unknown unless truly unclassifiable.
   - tech: AI, ML, coding, software, github, programming, models, LLM, tools
   - entertainment: games, movies, music, sports, anime, streaming
   - business: startups, finance, marketing, entrepreneurship, money
   - lifestyle: fitness, food, travel, fashion, productivity, motivation
   - education: courses, learning, tutorials, skills, career
   - news: breaking news, latest updates, announcements, releases
   Examples:
   - "claude fable 5" → tech
   - "ML projects" → tech
   - "fable game" → entertainment
   - "discipline motivation" → lifestyle

3. search_query: Write a specific, targeted search query a journalist would use.
   Include: year (2025 or 2026), specific names, action words
   Examples:
   - "machine learning projects" → "best machine learning projects build portfolio github 2025"
   - "claude fable 5" → "claude fable 5 review features how to use 2025"
   - "discipline motivation" → "discipline motivation content creators instagram viral 2025"

4. content_intent: What does the user actually want to POST about?
   - "showcase" = show off projects/tools to audience
   - "educate" = teach audience how to use something
   - "news" = share latest updates/announcements
   - "inspire" = motivate/inspire audience
   - "review" = give opinion on something

5. item_kind: If the user asks for a specific COUNT of DISCRETE, INDIVIDUALLY NAMED things
   (not sub-aspects of one broader topic), name what kind of thing each one should be, in a
   few words. Otherwise return "".
   Examples:
   - "5 different APIs for AI engineers" → "a named API or protocol"
   - "3 diet plans for weight loss" → "a named diet plan"
   - "4 startup ideas" → "a named startup idea"
   - "explain machine learning" → "" (sub-concepts of one topic, not discrete named things)
   - "top 5 exercises for abs" → "a named exercise movement"

USER PROMPT: "{cleaned_text}"{known_str}

Return ONLY this JSON, nothing else:
{{
  "category": "<tech|business|lifestyle|entertainment|education|news>",
  "core_topic": "<actual subject only, 2-5 words max>",
  "content_intent": "<showcase|educate|news|inspire|review>",
  "platform": "<instagram|youtube|tiktok|linkedin|facebook>",
  "post_count": <1-10>,
  "content_type": "<posts|script|thread|carousel>",
  "special_requests": [<strings>],
  "item_kind": "<see rule 5 above, or empty string>",
  "search_query": "<specific targeted search query with year>",
  "search_query_2": "<alternative search angle, different keywords>",
  "search_query_3": "<third angle, e.g. site:github.com or reddit.com>"
}}"""


def _parse_llm_json(text: str) -> dict:
    if not text:
        return {}
    try:
        cleaned = text.strip().strip("```json").strip("```").strip()
        return json.loads(cleaned)
    except Exception:
        pass
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        pass
    try:
        fixed = re.sub(r',\s*([}\]])', r'\1', text)
        fixed = fixed.replace("'", '"')
        fixed = re.sub(r'//.*?\n', '\n', fixed)
        start = fixed.index("{")
        end = fixed.rindex("}") + 1
        return json.loads(fixed[start:end])
    except Exception:
        pass
    try:
        result = {}
        field_patterns = {
            "core_topic":   r'"core_topic"\s*:\s*"([^"]{1,80})"',
            "platform":     r'"platform"\s*:\s*"([^"]{1,20})"',
            "post_count":   r'"post_count"\s*:\s*(\d+)',
            "content_type": r'"content_type"\s*:\s*"([^"]{1,20})"',
            "category":     r'"category"\s*:\s*"([^"]{1,30})"',
            "search_query": r'"search_query"\s*:\s*"([^"]{1,150})"',
        }
        for field, pattern in field_patterns.items():
            match = re.search(pattern, text)
            if match:
                val = match.group(1)
                result[field] = int(val) if field == "post_count" else val
        sr_match = re.search(r'"special_requests"\s*:\s*\[([^\]]*)\]', text)
        if sr_match:
            result["special_requests"] = re.findall(r'"([^"]+)"', sr_match.group(1))
        if result.get("core_topic"):
            return result
    except Exception:
        pass
    return {}


class IntentExtractor:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=CONFIG.models.groq_api_key)
        return self._client

    def extract(self, state: TrendForgeState, pre_extracted: dict) -> TrendForgeState:
        add_log(state, "[IntentExtractor] Starting LLM intent extraction...")

        cleaned_text = pre_extracted.get("cleaned_text", state["raw_prompt"])
        user_prompt = _build_intent_prompt(cleaned_text, pre_extracted)

        llm_result = {}
        tokens_used = 0

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=CONFIG.models.groq_model_small,
                temperature=CONFIG.models.routing_temperature,
                max_tokens=1500,
                reasoning_effort="low",
                messages=[
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            )
            raw_response = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            llm_result = _parse_llm_json(raw_response)
            add_log(state, f"[IntentExtractor] LLM responded — {tokens_used} tokens used.")

        except Exception as e:
            add_error(state, f"[IntentExtractor] LLM call failed: {e} — using rule fallback.")
            add_log(state, "[IntentExtractor] Falling back to rule-extracted data only.")

        add_tokens(state, "prompt_parsing", tokens_used)
        state = self._merge_into_state(state, pre_extracted, llm_result)

        add_log(state, f"[IntentExtractor] Final intent — topic='{state['core_topic']}' "
                       f"platform={state['platform']} posts={state['post_count']} "
                       f"category={state['detected_category']} intent={state['content_intent']}")
        return state

    def _merge_into_state(self, state: TrendForgeState, rules: dict, llm: dict) -> TrendForgeState:
        add_log(state, f"[IntentExtractor] LLM content_intent raw value: {llm.get('content_intent', 'NOT FOUND')}")

        raw_topic = llm.get("core_topic") or self._extract_simple_topic(
            rules.get("cleaned_text", state["raw_prompt"])
        )
        cleaned_topic = _strip_topic_filler(raw_topic)
        state["core_topic"] = cleaned_topic if len(cleaned_topic) > 3 else raw_topic

        rule_platform = rules.get("detected_platform", "")
        state["platform"] = rule_platform if rule_platform in SUPPORTED_PLATFORMS else "instagram"

        llm_val = llm.get("post_count")
        rule_val = rules.get("detected_post_count")
        if llm_val and str(llm_val).isdigit():
            final_count = int(llm_val)
        elif rule_val and str(rule_val).isdigit():
            final_count = int(rule_val)
        else:
            final_count = 5
        state["post_count"] = final_count if 1 <= final_count <= 20 else 5

        state["content_type"] = rules.get("detected_content_type") or llm.get("content_type") or "posts"

        llm_category = llm.get("category", "unknown")
        valid_categories = ["tech", "business", "lifestyle", "entertainment", "education", "news", "unknown"]
        state["detected_category"] = llm_category if llm_category in valid_categories else "unknown"

        valid_intents = ["showcase", "educate", "news", "inspire", "review"]
        llm_intent = llm.get("content_intent")
        if llm_intent in valid_intents:
            state["content_intent"] = llm_intent
        else:
            fallback_intent = CATEGORY_DEFAULT_INTENT.get(state["detected_category"], "showcase")
            add_log(state, f"[IntentExtractor] content_intent missing/invalid from LLM — "
                           f"defaulting to '{fallback_intent}' based on category='{state['detected_category']}'")
            state["content_intent"] = fallback_intent

        rule_requests = set(rules.get("detected_special_requests", []))
        llm_requests = set(llm.get("special_requests", []))
        state["special_requests"] = list(rule_requests | llm_requests)

        q1 = llm.get("search_query", state["core_topic"])
        q2 = llm.get("search_query_2", "")
        q3 = llm.get("search_query_3", "")
        queries = [q for q in [q1, q2, q3] if q]
        state["fetch_summary"] = q1
        state["search_queries"] = queries
        add_log(state, f"[IntentExtractor] Search queries generated: {queries}")

        state["is_long_prompt"] = rules.get("is_long", len(state["raw_prompt"]) > 120)

        state["item_kind"] = (llm.get("item_kind") or "").strip()

        return state

    def _extract_simple_topic(self, text: str) -> str:
        cleaned = _strip_topic_filler(text.lower())
        words = cleaned.split()
        return ' '.join(words[:6]) if words else text[:50]