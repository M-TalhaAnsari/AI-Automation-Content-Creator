"""
understanding/intent_extractor.py — LLM-Powered Intent Extractor

Uses Groq (fast, cheap model) to extract structured intent from any prompt —
short, long, ambiguous, or multilingual. Fills in whatever prompt_cleaner.py's
pure-rules pass couldn't determine (topic meaning, category, content intent).

Token budget: ~200-800 tokens per call depending on prompt complexity.
"""

import json
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CONFIG, SUPPORTED_PLATFORMS
from core.state import TrendForgeState, add_log, add_error, add_tokens


# ─────────────────────────────────────────────
# SHARED NOISE WORDS — the ONE place topic-cleaning filler is defined.
# Used by both _merge_into_state (primary path) and _extract_simple_topic
# (fallback path when the LLM call fails entirely). Do not duplicate this
# list elsewhere — if a new filler word needs handling, add it here only.
# ─────────────────────────────────────────────

TOPIC_FILLER_PATTERN = (
    r'\b(any|some|top|best|latest|new|give me|i want|i need|for my|please|'
    r'can you|could you|help me|create|make|build|generate|instagram|'
    r'youtube|tiktok|linkedin|post|content|news about|topic|related to|'
    r'that i|that make|for)\b'
)

TRAILING_WORD_PATTERN = r'\s+(to|and|or|the|a|an|with|by|in|on|at)$'


def _strip_topic_filler(text: str) -> str:
    """
    The ONE function that strips filler words from a topic string.
    Called from both the main LLM-merge path and the no-LLM fallback path.
    """
    cleaned = re.sub(TOPIC_FILLER_PATTERN, '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(TRAILING_WORD_PATTERN, '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned


# ─────────────────────────────────────────────
# CONTENT INTENT FALLBACK — the ONE place this default logic lives.
#
# "showcase" is NOT a safe universal default — its entire generation
# branch (generation/prompts.py) assumes a developer project with a real
# GitHub repo ("Tech Stack breakdown", "comment X for the repo link").
# When the LLM's classification call fails to return content_intent at
# all (a real, observed Groq JSON-reliability failure, not hypothetical —
# confirmed via a live run where "morning productivity habits" fell back
# to showcase and produced fake developer-project posts for a lifestyle
# topic), the fallback should be informed by whatever detected_category
# WAS successfully resolved, not blindly assume tech/showcase regardless.
#
# This mapping is a reasonable starting default, not a definitive one —
# revisit if a category's fallback still feels wrong in practice.
# ─────────────────────────────────────────────

CATEGORY_DEFAULT_INTENT = {
    "tech":           "showcase",
    "business":       "news",
    "lifestyle":      "inspire",
    "entertainment":  "review",
    "education":      "educate",
    "news":           "news",
    "unknown":        "showcase",
}


# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

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

USER PROMPT: "{cleaned_text}"{known_str}

Return ONLY this JSON, nothing else:
{{
  "category": "<tech|business|lifestyle|entertainment|education|news>",
  "core_topic": "<actual subject only, 2-5 words max>",
  "content_intent": "<showcase|educate|news|inspire|review>",
  "platform": "<instagram|youtube|tiktok|linkedin>",
  "post_count": <1-10>,
  "content_type": "<posts|script|thread|carousel>",
  "special_requests": [<strings>],
  "search_query": "<specific targeted search query with year>",
  "search_query_2": "<alternative search angle, different keywords>",
  "search_query_3": "<third angle, e.g. site:github.com or reddit.com>"
}}"""


def _parse_llm_json(text: str) -> dict:
    """
    Multi-strategy JSON parser. Never crashes — always returns something usable.
    Strategy order: direct parse → block extract → fix common mistakes → regex fallback.
    """
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
    """
    Groq-powered intent extractor. Combines rule-based pre-extraction
    (prompt_cleaner.py) with LLM semantic understanding.
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=CONFIG.models.groq_api_key)
        return self._client

    def extract(self, state: TrendForgeState, pre_extracted: dict) -> TrendForgeState:
        """Main entry point — merges rule-based data with LLM intelligence into state."""
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
                max_tokens=800,
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
        """
        Merges rule-extracted data and LLM data into state.
        Each field below has ONE clear priority order — see inline comments.
        No field should be assigned more than once; if you need to change
        priority logic, edit it here, not by adding a second assignment.
        """
        add_log(state, f"[IntentExtractor] LLM content_intent raw value: {llm.get('content_intent', 'NOT FOUND')}")

        # ── core_topic: LLM understands meaning best; fallback strips noise manually ──
        raw_topic = llm.get("core_topic") or self._extract_simple_topic(
            rules.get("cleaned_text", state["raw_prompt"])
        )
        cleaned_topic = _strip_topic_filler(raw_topic)
        state["core_topic"] = cleaned_topic if len(cleaned_topic) > 3 else raw_topic

        # ── platform: RULES ARE THE ONLY AUTHORITY. ─────────────────────────
        # LLM must never override this — LLM previously mis-guessed "linkedin"
        # for professional-sounding prompts even when the user never mentioned
        # any platform. If the user didn't explicitly name one, default to
        # instagram rather than let the LLM guess.
        rule_platform = rules.get("detected_platform", "")
        state["platform"] = rule_platform if rule_platform in SUPPORTED_PLATFORMS else "instagram"

        # ── post_count: trust LLM's contextual understanding over blind regex ──
        # (LLM correctly distinguishes "3 projects, each in 1 sentence" = post_count 3,
        #  which a naive regex would misread as post_count 1)
        llm_val = llm.get("post_count")
        rule_val = rules.get("detected_post_count")
        if llm_val and str(llm_val).isdigit():
            final_count = int(llm_val)
        elif rule_val and str(rule_val).isdigit():
            final_count = int(rule_val)
        else:
            final_count = 5
        state["post_count"] = final_count if 1 <= final_count <= 20 else 5

        # ── content_type: rules first (explicit keywords), LLM as fallback ──
        state["content_type"] = rules.get("detected_content_type") or llm.get("content_type") or "posts"

        # ── category: LLM decides (semantic judgment, not keyword matching) ──
        llm_category = llm.get("category", "unknown")
        valid_categories = ["tech", "business", "lifestyle", "entertainment", "education", "news", "unknown"]
        state["detected_category"] = llm_category if llm_category in valid_categories else "unknown"

        # ── content_intent: determines HOW content is generated downstream ──
        # Fallback is category-aware, not a blind "showcase" default — see
        # CATEGORY_DEFAULT_INTENT's docstring for why this matters. A missing
        # content_intent from the LLM is a real, observed failure mode (Groq's
        # JSON output can omit fields), not just a hypothetical edge case.
        valid_intents = ["showcase", "educate", "news", "inspire", "review"]
        llm_intent = llm.get("content_intent")
        if llm_intent in valid_intents:
            state["content_intent"] = llm_intent
        else:
            fallback_intent = CATEGORY_DEFAULT_INTENT.get(state["detected_category"], "showcase")
            add_log(state, f"[IntentExtractor] content_intent missing/invalid from LLM — "
                           f"defaulting to '{fallback_intent}' based on category='{state['detected_category']}'")
            state["content_intent"] = fallback_intent

        # ── special_requests: union of both sources, no conflict possible ──
        rule_requests = set(rules.get("detected_special_requests", []))
        llm_requests = set(llm.get("special_requests", []))
        state["special_requests"] = list(rule_requests | llm_requests)

        # ── search queries: LLM generates up to 3 angles for the fetch layer ──
        q1 = llm.get("search_query", state["core_topic"])
        q2 = llm.get("search_query_2", "")
        q3 = llm.get("search_query_3", "")
        queries = [q for q in [q1, q2, q3] if q]
        state["fetch_summary"] = q1
        state["search_queries"] = queries
        add_log(state, f"[IntentExtractor] Search queries generated: {queries}")

        state["is_long_prompt"] = rules.get("is_long", len(state["raw_prompt"]) > 120)

        return state

    def _extract_simple_topic(self, text: str) -> str:
        """
        Last-resort topic extraction when the LLM call fails entirely.
        Uses the SAME shared filler pattern as the main path (_strip_topic_filler)
        so both paths agree on what counts as noise.
        """
        cleaned = _strip_topic_filler(text.lower())
        words = cleaned.split()
        return ' '.join(words[:6]) if words else text[:50]