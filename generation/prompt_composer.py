"""generation/prompt_composer.py -- combines one IntentStrategy's guidance
with one PlatformStrategy's structure into the single final prompt string
sent to the LLM. This is the ONLY file that knows about both strategy
families at once -- individual intent/platform strategies never reference
each other, keeping the two axes genuinely independent.
"""
import html

from generation.intents.registry import get_intent_strategy
from generation.platforms.registry import get_platform_strategy


def compose_prompt(state: dict) -> str:
    platform_name = state.get("platform", "instagram")
    content_intent = state.get("content_intent", "showcase")

    intent_strategy = get_intent_strategy(content_intent)
    platform_strategy = get_platform_strategy(platform_name)

    guidance = intent_strategy.get_guidance(state)
    ps = platform_strategy.tone_settings()
    post_count = platform_strategy.effective_post_count(
        state.get("post_count", 5), state.get("post_count_explicit", False),
    )

    topic = state.get("core_topic", "")
    fetched = state.get("fetched_data", {})
    raw_user_intent = state.get("raw_prompt", state.get("user_prompt", topic))
    already_covered = state.get("already_covered", [])

    data_sections = []
    for source, items in fetched.items():
        if not items:
            continue
        lines = [f"[{source.upper()}]"]
        for item in items[:5]:
            title = item.get("title", item.get("name", ""))
            url = item.get("link", "")
            desc = item.get("summary", item.get("description", item.get("snippet", "")))
            title = html.unescape(str(title)).strip()
            desc = html.unescape(str(desc)).strip()
            if len(title) > 100:
                title = title[:97].rstrip() + "..."
            stars = item.get("stars", "")
            star_str = f" (Rating/Stars: {stars})" if stars else ""
            lines.append(f"  - {title}{star_str}: {str(desc)[:500]} | {url}")
        data_sections.append("\n".join(lines))
    data_block = "\n\n".join(data_sections) if data_sections else f"Topic: {topic} (No live web data available — use your internal knowledge base)"

    caption_guide = platform_strategy.wrap_caption_guide(guidance.caption_guide)

    item_kind = state.get("item_kind", "")
    item_instruction = guidance.item_instruction
    if item_kind:
        item_instruction += (
            f" Each of the {post_count} slots MUST be a distinct, individually-nameable "
            f"{item_kind} — not a related practice, technique, or adjacent concept that merely "
            f"relates to the topic."
        )

    def _build_slot(n):
        return f"""    {{
        "number": {n},
        "title": "<{guidance.title_guide}>",
        "hook": "<{guidance.hook_guide}>",
        "summary": {guidance.summary_guide},
        "link": "<{guidance.link_guide}>",
        "caption": "<{caption_guide}>",
        "hashtags": ["tag1", "tag2", "tag3"]
        }}"""

    post_slots = ",\n".join(_build_slot(i + 1) for i in range(post_count))

    avoid_block = ""
    if already_covered:
        covered_lines = "\n".join(f"  - {c['title']}" for c in already_covered if c.get("title"))
        avoid_block = f"""

    **AVOID REPEATING THESE (already covered in recent sessions on this topic/platform):**
    {covered_lines}
    Do not reuse these exact titles or angles — find distinct ones."""

    correction_block = ""
    retry_count = state.get("generation_retry_count", 0)
    validation_errors = state.get("generation_validation_errors", [])
    if retry_count > 0 and validation_errors:
        errors_text = "\n".join(f"  - {e}" for e in validation_errors[:8])
        correction_block = f"""

    **FIX THESE SPECIFIC ISSUES FROM YOUR PREVIOUS ATTEMPT (retry {retry_count}):**
    {errors_text}
    Correct every issue listed above in this new attempt — do not repeat the same mistakes."""

    return f"""You are an elite technical content strategist. Create {post_count} distinct {platform_name} posts based on the real data provided below.

    PLATFORM: {platform_name}
    TONE ARCHETYPE: {ps['tone']}
    HOOK PATTERN: {ps['hook_style']}
    EMOJI RULES: {ps['emoji_usage']}
    STRUCTURE: {platform_strategy.structure_note()}

    **USER'S ORIGINAL RAW REQUEST (Obey all implicit desires, explicit hooks, and phrasing rules hidden here):**
    "{raw_user_intent}"

    CONTENT STRATEGY:
    {guidance.intent_instruction}

    **REAL SOURCE DATA:**
    {data_block}
    {avoid_block}
    {correction_block}

    **CORE INSTRUCTIONS:**
    1. **Analyze User Intent:** Completely read the raw request above. If they asked to include specific lines like "This docker's concept will never fail you interview", build the post architecture specifically around that constraint.
    2. {item_instruction}
    3. **Structured Caption Layout:** Write clean, spaced, highly comprehensive paragraphs. Do not skip engineering details to save space.
    4. **Enforce JSON Array Boundaries:** Do NOT print hashtags inside the "caption" text field. Put all generated tags cleanly inside the "hashtags" array.
    5. **MANDATORY:** You must fill out exactly {post_count} post slots matching the JSON structure.

    Return your exact output using this JSON template — fill all {post_count} slots cleanly:
    {{
    "posts": [
    {post_slots}
    ],
    "series_hook": "<1-sentence teaser for the entire series>",
    "trend_insight": "<2-3 sentences explaining why this specific topic drives high organic saves right now>"
    }}"""