"""
understanding/intent_extractor.py — LLM-Powered Intent Extractor

Rewritten against ARCHITECTURE.md §3 / agents/02_intent_agent.md:
  - No longer constructs its own Groq client — goes through
    llm/client.py::call_groq(schema=IntentSchema) exclusively. This
    file no longer imports `groq` at all.
  - No longer hand-parses JSON (_parse_llm_json deleted) — the gateway
    validates against IntentSchema and raises LLMSchemaViolation on a
    bad response instead of us guessing at malformed JSON with regex
    repair passes.
  - core_topic is no longer re-cleaned with local regex
    (_strip_topic_filler / TOPIC_FILLER_PATTERN / TRAILING_WORD_PATTERN
    deleted) — the LLM's own core_topic is treated as final, per
    agents/02_intent_agent.md rule 1 ("this is the ONLY place
    topic-cleaning happens").
  - `platform` is no longer requested from the LLM at all. This is a
    no-op for behavior, not just a schema trim: _merge_into_state below
    never read `llm.get("platform")` even before this rewrite, only
    `rules["detected_platform"]` — so the field was already dead on
    arrival, just still being paid for in tokens.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Config.config import CONFIG, SUPPORTED_PLATFORMS
from core.state import TrendForgeState, add_log, add_error, add_tokens
from llm.client import call_groq
from llm.schemas import IntentSchema
from llm.errors import LLMCallFailed, LLMSchemaViolation


CATEGORY_DEFAULT_INTENT = {
    "tech":           "showcase",
    "business":       "news",
    "lifestyle":      "inspire",
    "entertainment":  "review",
    "education":      "educate",
    "news":           "news",
    "unknown":        "showcase",
}


# Stable across every call, so it belongs in `system` — not rebuilt and
# repeated inside `user` on every single request the way the old
# _build_intent_prompt() did. Rules 1-6 below are copied from
# agents/02_intent_agent.md's "System prompt (tightened)" as-is.
#
# One addition NOT in that spec, kept deliberately: the post_count
# formatting-number guardrail right below. agents/02 doesn't mention
# it, but doesn't contradict it either, and it's guarding against a
# specific real failure mode already worked out in production
# (miscounting "1 line" / "2 sentences" as post_count). Dropping it
# looked like an accidental loss from the rewrite, not an intentional
# simplification — flagging this choice rather than deciding it
# silently either way.
INTENT_SYSTEM_PROMPT = """You are a precise intent extraction engine for a social media content system.
Your job: understand what the user ACTUALLY wants to post about and
extract clean structured intent. Return output via the provided schema only.

CRITICAL INSTRUCTIONS FOR `post_count`:
- This refers to the number of distinct items (posts/projects/slides) to create.
- Default to 5.
- IGNORE numbers that refer to formatting (e.g., "1 line", "2 sentences", "3 words", "4 paragraphs").
- If the user says "give me 3 projects, each in 1 sentence", the post_count is 3, NOT 1.

RULES:

1. core_topic: Extract ONLY the actual subject. Remove all meta-words like
   "I want", "give me", "top", "best", "latest", "news about", "for my
   instagram". This is the ONLY place topic-cleaning happens — treat your
   own output here as final, not a draft something downstream will re-clean.
   - "I want top 5 ML projects for instagram" -> "machine learning projects"
   - "what is the latest news about claude fable 5" -> "claude fable 5"
   - "best python libraries for beginners" -> "python libraries beginners"
   Do NOT strip words that are part of a proper noun or title even if they
   overlap with filler vocabulary (e.g. "Top Gun Maverick" keeps "Top";
   "Best Practices" as a named framework keeps "Best").

2. category: decisive, never "unknown" unless truly unclassifiable.
   - tech: AI, ML, coding, software, github, programming, models, LLM, tools
   - entertainment: games, movies, music, sports, anime, streaming
   - business: startups, finance, marketing, entrepreneurship, money
   - lifestyle: fitness, food, travel, fashion, productivity, motivation
   - education: courses, learning, tutorials, skills, career
   - news: breaking news, latest updates, announcements, releases

3. search_query: specific, targeted, includes year 2025/2026 and named
   entities where relevant.

4. content_intent: showcase / educate / news / inspire / review
   - "showcase" = show off projects/tools to audience
   - "educate" = teach audience how to use something
   - "news" = share latest updates/announcements
   - "inspire" = motivate/inspire audience
   - "review" = give opinion on something

5. item_kind — the rule most retries come from. Name what kind of thing
   each item should be ONLY if the user asked for discrete, individually
   named things. Otherwise return "".
   Clear discrete cases:
   - "5 different APIs for AI engineers" -> "a named API or protocol"
   - "4 startup ideas" -> "a named startup idea"
   Clear non-discrete cases:
   - "explain machine learning" -> "" (sub-concepts of one topic)
   AMBIGUOUS MIDDLE — disambiguate with this rule: if each item would
   naturally need its own distinct proper name or title, it's discrete;
   if the items are just numbered aspects/steps of the same underlying
   idea, it's not.
   - "5 productivity tips" -> "" (tips are aspects of one topic, rarely
     individually-named things — unless the prompt names a source like
     "5 productivity tips from famous CEOs", which makes each one
     attributable/discrete -> "a named tip attributed to a specific person")
   - "3 diet plans for weight loss" -> "a named diet plan" (each diet
     plan IS individually nameable: keto, intermittent fasting, etc.)
   - "5 exercises for abs" -> "a named exercise movement" (each one has
     its own name: crunches, planks, etc.)

6. post_count_explicit: true only if the user stated an actual number
   ("5 posts", "one more"); false if you are defaulting.""".strip()


def _build_user_prompt(cleaned_text: str, pre_extracted: dict) -> str:
    """Per-request content only. The stable rules live in
    INTENT_SYSTEM_PROMPT above and are no longer rebuilt on every
    call the way the old _build_intent_prompt() did."""
    already_known = []
    if pre_extracted.get("detected_platform"):
        already_known.append(f'platform="{pre_extracted["detected_platform"]}"')
    if pre_extracted.get("detected_post_count"):
        already_known.append(f'post_count={pre_extracted["detected_post_count"]}')
    if pre_extracted.get("detected_special_requests"):
        already_known.append(f'special_requests={pre_extracted["detected_special_requests"]}')
    known_str = (
        f"\nAlready known from rule-based pre-extraction: {'; '.join(already_known)}"
        if already_known else ""
    )

    return f'USER PROMPT: "{cleaned_text}"{known_str}'


class IntentExtractor:
    def extract(self, state: TrendForgeState, pre_extracted: dict) -> TrendForgeState:
        add_log(state, "[IntentExtractor] Starting LLM intent extraction...")

        cleaned_text = pre_extracted.get("cleaned_text", state["raw_prompt"])
        user_prompt = _build_user_prompt(cleaned_text, pre_extracted)

        llm_result: dict = {}
        tokens_used = 0

        try:
            result = call_groq(
                system=INTENT_SYSTEM_PROMPT,
                user=user_prompt,
                model=CONFIG.models.groq_model_small,
                schema=IntentSchema,
                temperature=CONFIG.models.routing_temperature,
                reasoning_effort="low",
            )
            llm_result = result.content
            tokens_used = result.tokens_used
            add_log(state, f"[IntentExtractor] LLM responded — {tokens_used} tokens used.")

        except LLMSchemaViolation as e:
            # Per agents/02_intent_agent.md's "Must NOT do": no
            # prose-repair cascade here. Degrade to the rule-based
            # fallback in _merge_into_state and move on.
            add_error(state, f"[IntentExtractor] LLM response failed schema validation: {e} — using rule fallback.")
            add_log(state, "[IntentExtractor] Falling back to rule-extracted data only.")
        except LLMCallFailed as e:
            add_error(state, f"[IntentExtractor] LLM call failed: {e} — using rule fallback.")
            add_log(state, "[IntentExtractor] Falling back to rule-extracted data only.")
        except Exception as e:
            # Anything outside the gateway's own documented exceptions
            # (e.g. a Config/import problem) — same degrade-gracefully
            # posture as above, just not a gateway-specific failure.
            add_error(state, f"[IntentExtractor] Unexpected error: {e} — using rule fallback.")
            add_log(state, "[IntentExtractor] Falling back to rule-extracted data only.")

        add_tokens(state, "prompt_parsing", tokens_used)
        state = self._merge_into_state(state, pre_extracted, llm_result)

        add_log(state, f"[IntentExtractor] Final intent — topic='{state['core_topic']}' "
                       f"platform={state['platform']} posts={state['post_count']} "
                       f"category={state['detected_category']} intent={state['content_intent']}")
        return state

    def _merge_into_state(self, state: TrendForgeState, rules: dict, llm: dict) -> TrendForgeState:
        add_log(state, f"[IntentExtractor] LLM content_intent raw value: {llm.get('content_intent', 'NOT FOUND')}")

        # FIX: no more _strip_topic_filler pass here. A successful call
        # already validated core_topic through IntentSchema — re-cleaning
        # it here was exactly the duplication agents/02 rule 1 forbids.
        # If llm is {} (call failed entirely), _extract_simple_topic is
        # the documented fallback.
        state["core_topic"] = llm.get("core_topic") or self._extract_simple_topic(
            rules.get("cleaned_text", state["raw_prompt"])
        )

        rule_platform = rules.get("detected_platform", "")
        state["platform"] = rule_platform if rule_platform in SUPPORTED_PLATFORMS else "instagram"

        # NOTE: on a successful call, IntentSchema already guarantees
        # post_count is an int in [1, 10] before it ever reaches this
        # function — the isdigit()/range logic below is now only
        # load-bearing for the llm == {} fallback path (rule_val comes
        # from Agent 1's plain regex, which has no such guarantee).
        # Left as-is rather than trimmed since simplifying it wasn't
        # part of the requested fix and it's harmless on the success
        # path — flagging the redundancy, not silently cutting it.
        llm_val = llm.get("post_count")
        rule_val = rules.get("detected_post_count")
        if llm_val and str(llm_val).isdigit():
            final_count = int(llm_val)
        elif rule_val and str(rule_val).isdigit():
            final_count = int(rule_val)
        else:
            final_count = 5
        # STILL OPEN (flagged last turn, not resolved here): this clamps
        # to 20, but IntentSchema clamps the LLM's own answer to 10.
        # Pick one when you're ready and I'll make both sides match.
        state["post_count"] = final_count if 1 <= final_count <= 20 else 5

        # rule_val only exists when the regex-based cleaner found a real
        # number in the raw text, which is a more reliable "explicit"
        # signal than the LLM's own self-report, so it's checked first;
        # the LLM's flag is a fallback for numbers phrased in ways the
        # regex misses (e.g. "one more", "a couple").
        rule_count_detected = bool(rule_val) and str(rule_val).isdigit()
        llm_explicit_flag = bool(llm.get("post_count_explicit"))
        state["post_count_explicit"] = rule_count_detected or llm_explicit_flag

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
        """LLM-call-failed fallback only. `text` is expected to already
        be Agent 1's noise-stripped `cleaned_text`. Per
        agents/02_intent_agent.md's "Must NOT do" (fall back to Agent
        1's rule-based cleaned_text truncated to 6 words, don't build a
        second cleaning pass here), this truncates directly rather than
        reusing the now-deleted _strip_topic_filler."""
        words = text.split()
        return ' '.join(words[:6]) if words else text[:50]