from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class NewsIntent(BaseIntentStrategy):
    name = "news"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        return IntentGuidance(
            intent_instruction=(
                "The user wants to share LATEST NEWS, updates, or announcements about the topic. "
                "Report what actually happened using the fetched source data as your primary source of truth — "
                "do NOT invent developments, dates, or details that aren't grounded in the fetched data. "
                "If the fetched data is thin on a specific angle, stay general rather than fabricating specifics."
            ),
            item_instruction=(
                f"Each slot must cover ONE distinct angle or development related to '{topic}' — "
                "e.g. what was announced, what changed, what the community reaction is, what happens next. "
                "Never repeat the same news item across two slots."
            ),
            title_guide="Clear, factual headline describing the specific development covered in this slot",
            hook_guide="A breaking-news-style opening line — states what happened or what's new, creates urgency to know more",
            summary_guide='["What happened / what changed", "Why it matters right now", "What to watch next"]',
            link_guide=(
                "MUST be a real URL copied exactly from the source data above if this slot reports on a specific "
                'article/announcement. Empty string "" only if no single source maps to this slot.'
            ),
            caption_guide=(
                "Report the facts clearly and in order: what happened, when, and why it matters to the audience. "
                "If you go beyond what the source data states, phrase it as a genuine question or possibility "
                "woven naturally into the sentence (e.g. 'this could shift funding toward...', 'it remains to be "
                "seen whether...') — do NOT insert literal labels like the word 'Speculation' or bracketed asides "
                "into the caption text. End with a question inviting the audience's take on the development, not "
                "a repo/download CTA."
            ),
        )