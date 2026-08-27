"""generation/prompt_composer.py -- Combines IntentStrategy guidance with PlatformStrategy
structure into the final prompt sent to the LLM. Enforces viral social media formatting,
carousel slide sequencing, zero ALL-CAPS shouting, and user-prompt adaptability.
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
    total_items_count = sum(len(items) for items in fetched.values())
    per_source_cap = 6 if total_items_count <= 20 else 4
    for source, items in fetched.items():
        if not items:
            continue
        lines = [f"[{source.upper()}]"]
        for item in items[:per_source_cap]:
            title = item.get("title", item.get("name", ""))
            url = item.get("link", "")
            desc = item.get("summary", item.get("description", item.get("snippet", "")))
            title = html.unescape(str(title)).strip()
            desc = html.unescape(str(desc)).strip()
            if len(title) > 100:
                title = title[:97].rstrip() + "..."
            stars = item.get("stars", "")
            star_str = f" (Rating/Stars: {stars})" if stars else ""
            lines.append(f"  - {title}{star_str}: {str(desc)[:350]} | {url}")
        data_sections.append("\n".join(lines))
    data_block = "\n\n".join(data_sections) if data_sections else f"Topic: {topic} (No live web data available -- use your deep knowledge base)"

    caption_guide = platform_strategy.wrap_caption_guide(guidance.caption_guide)

    def _build_slot(n):
        return f"""    {{
        "number": {n},
        "title": "<Short, bold, visual-first slide headline (max 7-10 words) -- minimal text for on-screen graphic card>",
        "hook": "<1 punchy subtitle line (max 12 words) for the on-screen card>",
        "summary": [
            "1. <Short key point -- max 8 words>",
            "2. <Short key point -- max 8 words>",
            "3. <Short key point -- max 8 words>"
        ],
        "link": "<{guidance.link_guide}>",
        "caption": "<Full, high-value post description written in natural casing without ALL-CAPS words. Adapts to user instructions (bullet points vs spaced paragraphs).>",
        "hashtags": ["relevanttag1", "relevanttag2", "relevanttag3"]
        }}"""

    post_slots = ",\n".join(_build_slot(i + 1) for i in range(post_count))

    avoid_block = ""
    if already_covered:
        covered_lines = "\n".join(f"  - {c['title']}" for c in already_covered if c.get("title"))
        avoid_block = f"""

    **AVOID REPEATING THESE (already covered in recent sessions):**
    {covered_lines}
    Do not reuse these exact angles -- deliver distinct value."""

    return f"""You are an elite viral content creator with millions of organic impressions across Instagram, LinkedIn, and TikTok.
Create {post_count} distinct, platform-ready {platform_name} post cards or carousel slides based on the request and real data below.

    PLATFORM: {platform_name}
    TONE ARCHETYPE: {ps['tone']}
    HOOK PATTERN: {ps['hook_style']}
    EMOJI RULES: {ps['emoji_usage']}
    STRUCTURE: {platform_strategy.structure_note()}

    **USER'S ORIGINAL RAW REQUEST (Follow every explicit instruction, format preference, and theme requested here):**
    "{raw_user_intent}"

    CONTENT INTENT:
    {guidance.intent_instruction}

    **CRITICAL VIRAL CREATOR RULES (STRICT QUALITY GATES):**
    1. **MINIMAL ON-SCREEN TEXT (Visual Post Card):**
       On Instagram / social media, visual cards MUST NEVER have walls of text.
       - "title": Clean, high-impact headline (max 8-10 words).
       - "hook": Subtitle / curiosity hook (max 12 words).
       - "summary": 3 ultra-short, punchy bullet points (max 8-10 words each) designed to fit inside a visual graphic without clutter.
    2. **RICH & ENGAGING CAPTION / DESCRIPTION:**
       All the deep, valuable, step-by-step information belongs in the "caption" (description).
       - **Zero ALL-CAPS Words:** DO NOT write capitalized screaming labels like "PROJECT OVERVIEW:", "TECH STACK:", "WHAT HAPPENED:", "KEY INSIGHT:". Write naturally capitalized, human creator copy (e.g. "Here is how it works:", "The tech behind it:", "Why this matters today:").
       - **Format Adaptability:** If the user asked for bullet points or lists in their prompt, format the caption with clean spaced bullet points. If they asked for a story or breakdown, format with short, breathable 1-2 sentence paragraphs.
       - **No Walls of Text:** Use double line breaks between sections for effortless mobile readability.
       - **High-Conversion CTA:** End with an engagement prompt (e.g. "Save this for later", "Drop a comment if you want the link", "Which one is your favorite?").
    3. **MULTI-SLIDE CAROUSEL COHESION (If {post_count} > 1):**
       Each post slot can act either as a distinct post or a progressive slide in a carousel (Slide 1: Hook / Big Idea, Slide 2: Core Concept / Problem, Slide 3: Step-by-Step Breakdown, Slide 4: Key Nuance / Insight, Slide 5: Summary & CTA).
    4. **HASHTAG DISCIPLINE:**
       Place all hashtags strictly in the "hashtags" array. NEVER put hashtags inside the "caption" field.

    **REAL SOURCE DATA:**
    {data_block}
    {avoid_block}

    Return your exact output using this JSON template -- fill all {post_count} slots cleanly:
    {{
    "posts": [
    {post_slots}
    ],
    "series_hook": "<1-sentence curiosity-gap hook for the series that stops the scroll>",
    "trend_insight": "<2-3 sentences explaining why this topic performs exceptionally well right now>"
    }}"""
