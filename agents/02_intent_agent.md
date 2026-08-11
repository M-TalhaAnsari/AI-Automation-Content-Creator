# Agent 2 — IntentAgent

**Core question this agent answers:**
*"What does the user actually want to post about, and is it a request for
discrete individually-named items or a single decomposed topic?"*

- **Type:** LLM (Groq small model), structured output (tool-calling schema,
  not prose-then-parse).
- **LangGraph node:** Yes — `intent`, runs after `prompt_clean`.
- **File:** `understanding/intent_extractor.py`.
- **Calls through:** `llm/client.py::call_groq(schema=IntentSchema)`.

## Inputs
- `cleaned_text: str` (from Agent 1)
- `detected_platform`, `detected_post_count`, `detected_special_requests`
  (from Agent 1, passed as "already known" context, not re-derived)

## Output schema — `IntentSchema`
```
{
  "category": "tech|business|lifestyle|entertainment|education|news",
  "core_topic": str,              # 2-5 words, meta-words already stripped
                                   #   BY THE LLM — no downstream regex
                                   #   re-cleans this. See "Must NOT do."
  "content_intent": "showcase|educate|news|inspire|review",
  "post_count": int,               # 1-10
  "post_count_explicit": bool,     # see note below
  "content_type": "posts|script|thread|carousel",
  "special_requests": list[str],
  "item_kind": str,                # "" if not discrete named items
  "search_query": str,
  "search_query_2": str,
  "search_query_3": str
}
```
**Deliberately excludes `platform`.** The old prompt asked for a
`platform` field the merge step then silently discarded — no consumer
existed. Platform is Agent 1's job (deterministic keyword match); do not
re-add this field unless you also name the exact line of code that will
read it.

## System prompt (tightened)

```
You are a precise intent extraction engine for a social media content system.
Your job: understand what the user ACTUALLY wants to post about and
extract clean structured intent. Return output via the provided schema only.

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
   tech / entertainment / business / lifestyle / education / news —
   [keep existing category definitions + examples]

3. search_query: specific, targeted, includes year 2025/2026 and named
   entities where relevant.

4. content_intent: showcase / educate / news / inspire / review —
   [keep existing definitions]

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
   ("5 posts", "one more"); false if you are defaulting.

USER PROMPT: "{cleaned_text}"
Already known from rule-based pre-extraction: {known_str}
```

## post_count_explicit — merge note
`detected_post_count` (Agent 1, regex-based) is the higher-trust signal
when both exist, because it only fires on an unambiguous digit in the raw
text. The LLM's `post_count_explicit` flag is the fallback for phrasings
regex misses ("a couple", "one more"). Merge logic:
`explicit = bool(detected_post_count) or llm.post_count_explicit`.

## Must NOT do
- Must not re-clean `core_topic` downstream with regex. If bad topics are
  still showing up in practice, that is a signal to add a worked example
  to rule 1 above, not to add a second cleaning pass.
- Must not retry this call on a schema violation by prose-repair-parsing.
  A schema violation from `llm/client.py` is a hard error — log it, fall
  back to Agent 1's rule-based `cleaned_text` truncated to 6 words, and
  move on. Do not build a JSON-repair cascade here again.

## Downstream consumer
`GenerationAgent` (topic, content_intent, item_kind), `RouterAgent`
(category), `FetchQualityGate` (content_intent for link-required check).
