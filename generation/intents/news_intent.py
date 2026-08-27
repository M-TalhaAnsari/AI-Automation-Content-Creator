from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class NewsIntent(BaseIntentStrategy):
    name = "news"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        return IntentGuidance(
            intent_instruction=(
                "The user wants to share BREAKING NEWS and hot industry updates using a top creator voice. "
                "You are not a journalist -- you are a creator who breaks down what just happened and "
                "tells your audience WHY it matters to THEM, right now. "
                "Use the fetched source data as your primary source of truth. "
                "Do NOT invent dates, numbers, or details not present in the data. "
                "Write with urgency, clarity, and a point of view -- not a neutral wire-service report."
            ),
            item_instruction=(
                f"Each slot must cover ONE distinct new development related to '{topic}'. "
                "Cover: what happened, why it matters today, and what the audience should watch next. "
                "Never repeat the same development across two slots. "
                "Every post should make the reader feel informed and slightly ahead of the curve."
            ),
            title_guide=(
                "A clear, punchy breaking-news headline that states WHAT changed. "
                "Use present tense and active voice. "
                "Avoid clickbait vagueness -- be specific about the development. "
                "Example: 'OpenAI Just Killed the Paid Tier Model' or 'Meta Released a Free GPT-4 Alternative'"
            ),
            hook_guide=(
                "A 1-2 sentence breaking-news opener that creates urgency and makes the reader feel "
                "like they need to know this immediately. "
                "Pattern: 'This just happened in [field] -- and if you work in [area], pay attention:' / "
                "'[X] just changed. Here is what nobody is talking about yet:' / "
                "'The [industry] news this week is bigger than it looks. Here is why:'"
            ),
            summary_guide=(
                '["What happened: The specific development in one tight line", '
                '"Why it matters now: The real-world impact on the audience reading this", '
                '"What to watch next: The upcoming signal, trend, or consequence to track"]'
            ),
            link_guide=(
                "MUST be a real URL copied exactly from the source data if this slot reports on a specific "
                "article or announcement. Use empty string \"\" only if no single source maps to this slot. "
                "Never invent a URL."
            ),
            caption_guide=(
                "Write a tight, creator-voice news breakdown in 4 sections:\n"
                "1) HOOK (2 lines): Break the news with urgency and a creator POV.\n"
                "2) THE FACTS (3 bullets max): What actually happened -- specific, sourced, no fluff.\n"
                "3) WHY IT MATTERS (1-2 lines): Connect this directly to the audience's work or career.\n"
                "4) CTA: 'What is your take? Comment below.' or 'Save this before it gets buried.'\n"
                "Do NOT add speculation labels or bracketed editorial asides. "
                "If you go beyond the source, phrase it as natural creator language: "
                "'This could shift...' or 'Watch whether...' -- not [Speculation]. "
                "Never put hashtags inside the caption. Hard line breaks between sections."
            ),
        )
