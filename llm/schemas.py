"""
llm/schemas.py — Pydantic schema definitions for every structured LLM
call site in TrendForge (ARCHITECTURE.md §2).

Each model here does two jobs, from one definition:
  1. `Model.model_json_schema()` is what llm/client.py sends the
     provider (Groq's `response_format.json_schema.schema`, Gemini's
     `response_schema`).
  2. `Model.model_validate_json(...)` is what llm/client.py runs on
     whatever comes back, regardless of what the provider claims to
     have enforced. See llm/client.py's module docstring for why step
     2 isn't optional even when step 1 "worked."

Deliberately NOT here: a SelectionSchema. agents/10_selection_agent.md
confirms Agent 10 was merged into Agent 5 and no new schema was needed
for that merge — §2 of ARCHITECTURE.md still lists SelectionSchema in
its prose, but that's stale text left over from before the merge, not
a spec. Don't rebuild it without a concrete regression-set reason (see
agents/10's own "if you're tempted to re-split this" section).

Field `description=` text below (e.g. core_topic's word-count guidance)
is intentionally NOT a hard validation constraint. Per ARCHITECTURE.md
principle #2 ("structural checks are code, semantic checks are
prompts"): word count is a quality target for the model to aim for,
not a fact worth a hard schema rejection over — a legitimate one-word
topic ("Bitcoin") or a six-word proper noun shouldn't fail validation
over it. The description text still flows into the schema the
provider sees, so it's not lost as guidance — it's just not enforced
by model_validate_json.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


# ─────────────────────────────────────────────────────────────
# Agent 2 — IntentAgent  (agents/02_intent_agent.md)
# ─────────────────────────────────────────────────────────────

class IntentSchema(BaseModel):
    category: Literal[
        "tech", "business", "lifestyle", "entertainment", "education", "news"
    ]
    core_topic: str = Field(
        description=(
            "2-5 words, meta-words already stripped BY THE LLM — this is "
            "the only place topic-cleaning happens, treat it as final. Do "
            "not strip words that are part of a proper noun or title even "
            "if they overlap with filler vocabulary."
        )
    )
    content_intent: Literal["showcase", "educate", "news", "inspire", "review"]
    post_count: int = Field(ge=1, le=10, description="Number of distinct items to create.")
    post_count_explicit: bool = Field(
        description="True only if the user stated an actual number; false if defaulting."
    )
    content_type: Literal["posts", "script", "thread", "carousel"]
    special_requests: list[str] = Field(default_factory=list)
    item_kind: str = Field(
        default="",
        description=(
            'What kind of discrete, individually-named thing each item '
            'should be (e.g. "a named API or protocol"). Empty string if '
            'the request is not for discrete named items — see rule 5.'
        ),
    )
    search_query: str
    search_query_2: str = ""
    search_query_3: str = ""

    # Deliberately excludes `platform`. agents/02_intent_agent.md: the old
    # prompt asked for it and nothing downstream ever read it — platform
    # is owned entirely by understanding/prompt_cleaner.py's rule-based
    # detection, merged in upstream of this schema.

    # NOTE: post_count is capped at 10 here per agents/02_intent_agent.md's
    # explicit schema spec ("post_count: int, # 1-10"). The CURRENT
    # understanding/intent_extractor.py._merge_into_state clamps to 1-20
    # instead. That's a real inconsistency between the two, not something
    # I'm resolving here — flagging it, not fixing it silently, per
    # ARCHITECTURE.md §0.3. Whoever does the intent_extractor.py fix pass
    # needs to pick one and reconcile the other.


# ─────────────────────────────────────────────────────────────
# Agent 5 — GenerationAgent  (agents/05_generation_agent.md)
# Agent 10 (SelectionAgent) is merged into Agent 5 — see
# agents/10_selection_agent.md. No SelectionSchema; see module docstring.
# ─────────────────────────────────────────────────────────────

# Enforces the "^#" pattern GeneratedPostsSchema's hashtags field needs,
# replacing the old `t if t.startswith("#") else f"#{t}"` normalization
# loop in content_generator.py (fix #4). Behavior change worth knowing:
# a stray non-"#" hashtag used to be silently fixed in code; now it's a
# hard LLMSchemaViolation on that call, same as any other schema break.
Hashtag = Annotated[str, StringConstraints(pattern=r"^#")]


class PostItem(BaseModel):
    number: int
    title: str
    hook: str
    summary: list[str]
    link: str = Field(
        default="",
        description=(
            "Leave empty if no good source link exists — do not invent "
            "one. PostValidationGate strips any link that doesn't exactly "
            "match a URL present in fetched_data, unconditionally; this "
            "schema does not attempt that check, that's code's job."
        ),
    )
    caption: str
    hashtags: list[Hashtag] = Field(default_factory=list)


class EditSchema(BaseModel):
    """
    Output of conversation/actions.py's edit_existing (_edit_via_gemini /
    _edit_via_groq). Same post shape GenerationAgent produces, minus the
    two series-level fields that only make sense across a full new batch
    of posts (series_hook, trend_insight) — a single edited post has
    neither. GeneratedPostsSchema below extends this instead of
    duplicating it by hand, so the two can't quietly drift the way two
    independently hand-copied JSON-schema dicts could.
    """
    posts: list[PostItem]


class GeneratedPostsSchema(EditSchema):
    series_hook: str
    trend_insight: str


# ─────────────────────────────────────────────────────────────
# Agent 7 — ItemKindGate  (agents/07_item_kind_gate.md)
# ─────────────────────────────────────────────────────────────

class ItemKindCheckSchema(BaseModel):
    mismatched_indices: list[int] = Field(default_factory=list)
    reason: str