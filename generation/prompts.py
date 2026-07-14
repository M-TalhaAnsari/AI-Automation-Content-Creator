"""
generation/prompts.py — Dynamic Cross-Field Prompt Templates

A completely domain-agnostic prompt builder. Automatically detects the niche,
identifies the target audience, and shapes high-engagement, value-driven captions
for any field.

Implements all 5 content_intent values documented in core/state.py:
showcase | educate | news | inspire | review — each with its own
intent_instruction, item_instruction, and schema guidance (title/hook/
summary/link/caption). Previously only educate + a showcase-flavored
"else" existed; news/inspire/review silently fell through to showcase-
style "comment for the repo link" framing regardless of actual intent.

Also reads state["already_covered"] (populated in main.py via
memory/session_store.py's get_already_covered()) and injects an
avoid-repeating block into the prompt when prior sessions exist for this
topic + platform. Empty list is the normal "no history" case, not an error.
"""

import html
from config import PLATFORM_SETTINGS


def build_generation_prompt(state: dict) -> str:
    platform = state.get("platform", "instagram")
    ps = PLATFORM_SETTINGS.get(platform, PLATFORM_SETTINGS["instagram"])
    topic = state.get("core_topic", "")
    post_count = state.get("post_count", 5)
    fetched = state.get("fetched_data", {})

    raw_user_intent = state.get("raw_prompt", state.get("user_prompt", topic))
    content_intent = state.get("content_intent", "showcase")
    already_covered = state.get("already_covered", [])

    # Format data cleanly regardless of source type
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

    # ── content_intent → generation strategy ──────────────────────
    # Each branch defines the same 7 variables so the schema-building
    # code below never needs to know which intent it's dealing with.

    if content_intent == "educate":
        intent_instruction = (
            "The user wants high-value EDUCATIONAL content that breaks down core concepts of the topic clearly, "
            "for a general audience interested in the subject. "
            "Do NOT write project blueprints or instruct people to download a code repository. "
            "Use your deep knowledge base to explain the mechanics, principles, or reasoning behind the subject. "
            "Use the fetched source data as modern context, real-world proof, or baseline references. "
            "Only frame this around interviews, exams, or professional certification if the user's raw request "
            "explicitly asks for that (see CORE INSTRUCTIONS below) — otherwise explain the topic on its own "
            "terms, whatever domain it's in (technical, lifestyle, business, etc.)."
        )
        item_instruction = (
            f"Each of the generated slots must teach ONE distinct, foundational concept of '{topic}' "
            "independently — for a technical topic, distinct mechanisms or components (e.g., if Docker: "
            "Images vs Containers, Storage Volumes, Network Isolation); for a non-technical topic, distinct "
            "principles, techniques, or steps relevant to that subject."
        )
        title_guide = "Clean, high-impact concept name relevant to the topic's own domain — not necessarily technical (e.g., 'How Docker Isolation Actually Works' for a tech topic, or 'Why Morning Light Resets Your Cortisol' for a lifestyle topic)"
        hook_guide = "A powerful, authority-driven hook sentence establishing why this concept matters. If the user explicitly requested a specific line, theme, or framing (like interview prep) in their raw prompt, you MUST adapt and use that exact sentiment as your hook — otherwise keep the hook general-audience, not assuming any specific professional context."
        summary_guide = '["Core Sub-Concept Breakdown 1", "Underlying Mechanism or Principle 2", "Common Misconception or Pitfall 3"]'
        # Concept-first, not source-first — a given concept slot often has no
        # single real-world URL it maps to. Link stays optional here.
        link_guide = (
            'OPTIONAL — include a real URL copied exactly from the source data above ONLY if one directly '
            'supports this specific concept slot. If no single source maps cleanly to this concept, use an '
            'empty string "". Never invent a URL.'
        )
        caption_guide = (
            "Full multi-paragraph educational breakdown of this concept. Explain how it works at a systems level. "
            "Keep the language sharp, precise, and deeply technical so it reads perfectly for an engineer preparing for a technical round. "
            "End with a clear, engaging call-to-action that encourages saves or invites conceptual answers in the comments. Do not mention source code repos or downloading links."
        )

    elif content_intent == "news":
        intent_instruction = (
            "The user wants to share LATEST NEWS, updates, or announcements about the topic. "
            "Report what actually happened using the fetched source data as your primary source of truth — "
            "do NOT invent developments, dates, or details that aren't grounded in the fetched data. "
            "If the fetched data is thin on a specific angle, stay general rather than fabricating specifics."
        )
        item_instruction = (
            f"Each slot must cover ONE distinct angle or development related to '{topic}' — "
            "e.g. what was announced, what changed, what the community reaction is, what happens next. "
            "Never repeat the same news item across two slots."
        )
        title_guide = "Clear, factual headline describing the specific development covered in this slot"
        hook_guide = "A breaking-news-style opening line — states what happened or what's new, creates urgency to know more"
        summary_guide = '["What happened / what changed", "Why it matters right now", "What to watch next"]'
        link_guide = (
            "MUST be a real URL copied exactly from the source data above if this slot reports on a specific "
            'article/announcement. Empty string "" only if no single source maps to this slot.'
        )
        caption_guide = (
            "Report the facts clearly and in order: what happened, when, and why it matters to the audience. "
            "If you go beyond what the source data states, phrase it as a genuine question or possibility "
            "woven naturally into the sentence (e.g. 'this could shift funding toward...', 'it remains to be "
            "seen whether...') — do NOT insert literal labels like the word 'Speculation' or bracketed asides "
            "into the caption text. End with a question inviting the audience's take on the development, not "
            "a repo/download CTA."
        )

    elif content_intent == "inspire":
        intent_instruction = (
            "The user wants MOTIVATIONAL/INSPIRATIONAL content built around the topic. "
            "Use the fetched source data as supporting evidence or real-world proof points, but the emotional "
            "angle — not the raw facts — is the actual content. Make it feel personal and human, not corporate."
        )
        item_instruction = (
            f"Each slot must hit ONE distinct emotional angle or takeaway related to '{topic}' "
            "(e.g. overcoming a specific obstacle, a mindset shift, a concrete transformation). "
            "Avoid repeating the same emotional beat across multiple slots."
        )
        title_guide = "Short, emotionally resonant phrase capturing the core message of this slot"
        hook_guide = "An opening line that creates an immediate emotional connection — vulnerability, relatability, or a bold truth"
        summary_guide = '["The struggle or starting point", "The shift or insight", "The takeaway for the reader"]'
        link_guide = (
            'OPTIONAL — a real URL from the source data above may support this slot as proof, but is not required. '
            'Use empty string "" if nothing maps cleanly. Never invent a URL.'
        )
        caption_guide = (
            "Write in a warm, first-person, human voice — not a corporate tone. Tell a short story or make a "
            "direct, honest point tied to the emotional angle for this slot. End with a genuine question or "
            "call-to-reflection that invites the audience to share their own experience, not a repo/download CTA."
        )

    elif content_intent == "review":
        intent_instruction = (
            "The user wants an honest OPINION or REVIEW of the topic. "
            "Take a clear, specific stance — do not hedge into a neutral summary. Use the fetched source data "
            "as evidence for your position, but the point of view itself is the content."
        )
        item_instruction = (
            f"Each slot must cover ONE distinct aspect being evaluated about '{topic}' "
            "(e.g. one specific feature, one comparison point, one tradeoff) with a clear verdict on that aspect. "
            "Do not repeat the same evaluation angle across slots."
        )
        title_guide = "Specific aspect being reviewed in this slot, phrased with a clear point of view"
        hook_guide = "A bold, opinionated opening line that states the verdict or a strong claim upfront"
        summary_guide = '["What this aspect does / claims to do", "The honest verdict — good or bad", "Who this is actually good for (or not)"]'
        link_guide = (
            "MUST be a real URL copied exactly from the source data above if this slot's evaluation is based on "
            'a specific source. Empty string "" only if the point is a general opinion not tied to one source.'
        )
        caption_guide = (
            "State your verdict clearly and early — don't bury the opinion. Back it up with specific evidence "
            "from the source data. Acknowledge the strongest counterargument briefly, then restate your position. "
            "End with a direct question asking whether the audience agrees or disagrees, not a repo/download CTA."
        )

    else:
        # Default / true fallback: showcase (also covers any unexpected value)
        data_starved = state.get("data_starved", False)

        if data_starved:
            # No real project data survived fetching (even after retries) —
            # the CTA "comment X and I'll DM you the repo link" would be a
            # flat lie here, since there's no repo to send. Found via a real
            # forced-failure run: the model kept the fake-repo CTA anyway,
            # producing generic invented "project ideas" with a promise it
            # can't keep. Shift framing to honest concept pitches instead.
            intent_instruction = (
                "The user wants to showcase compelling PROJECT CONCEPTS related to the topic, but the fetched "
                "source data was insufficient or low-quality even after retries — treat these as original concept "
                "pitches drawn from your own knowledge, NOT as descriptions of a specific existing repository. "
                "Do not imply a real, ready-made codebase exists to hand over."
            )
            item_instruction = (
                "Each slot must pitch ONE distinct, plausible project concept. End each caption with a genuine "
                "engagement question or a 'would you build this?' style prompt — NOT a 'comment X and I'll DM "
                "you the repo' CTA, since no real repository exists behind this concept."
            )
            link_guide = (
                'Leave as an empty string "" — there is no real source to link to. Never invent a URL.'
            )
            caption_guide = (
                "Full multi-paragraph caption structured with: Concept Overview, Suggested Tech Stack, and how it "
                "could work — framed clearly as an idea/concept, not a real existing project. End with a genuine "
                "question inviting engagement, not a fake repo-DM CTA."
            )
        else:
            intent_instruction = (
                "The user wants to showcase epic, actionable, portfolio-grade project implementations designed to drive high engagement. "
                "Do NOT write generic tool overviews. Turn the source data into a concrete project build blueprint."
            )
            item_instruction = (
                "Each slot must focus entirely on ONE individual project implementation. Every single caption must end with a highly "
                "specific comment-bait CTA forcing engineers to comment a keyword to receive the repository link in their DMs."
            )
            link_guide = (
                "MUST be a real URL copied exactly from the source data above — never empty for showcase mode, never invented"
            )
            caption_guide = (
                "Full multi-paragraph caption structured with: Project Overview, Tech Stack breakdown, Core System Architecture, "
                "and a high-conversion Call-To-Action explicitly inviting users to comment a key word to get the GitHub link auto-sent to their DMs. Do not output hashtags here."
            )

        title_guide = f"Highly compelling, specific real-world project name built using {topic}"
        hook_guide = "Disruptive, curiosity-spiking hook sentence that grabs a developer's attention instantly"
        summary_guide = '["Core Technical Highlight 1", "Key System Asset 2", "Deployment Target 3"]'

    # ── Dynamic schema template injecting the context-aware guides ──
    def _build_slot(n):
        return f"""    {{
        "number": {n},
        "title": "<{title_guide}>",
        "hook": "<{hook_guide}>",
        "summary": {summary_guide},
        "link": "<{link_guide}>",
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

    return f"""You are an elite technical content strategist. Create {post_count} distinct {platform} posts based on the real data provided below.

    PLATFORM: {platform}
    TONE ARCHETYPE: {ps['tone']}
    HOOK PATTERN: {ps['hook_style']}
    EMOJI RULES: {ps['emoji_usage']}

    **USER'S ORIGINAL RAW REQUEST (Obey all implicit desires, explicit hooks, and phrasing rules hidden here):**
    "{raw_user_intent}"

    CONTENT STRATEGY:
    {intent_instruction}

    **REAL SOURCE DATA:**
    {data_block}
    {avoid_block}

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


SYSTEM_PROMPT = """You are a world-class viral content strategist and copywriter.
    You write highly engaging, value-dense educational copy with clear line breaks.
    You output your work exclusively in flawless, production-ready JSON matching the requested schema. Never output markdown ticks or conversational text outside the JSON structure."""