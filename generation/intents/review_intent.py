from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class ReviewIntent(BaseIntentStrategy):
    name = "review"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        return IntentGuidance(
            intent_instruction=(
                "The user wants BOLD OPINION content -- a creator taking a clear, specific stance. "
                "You are not writing a balanced Wikipedia summary. "
                "You are a creator with a strong point of view who uses evidence to back a verdict. "
                "Use the fetched source data as evidence for your position. "
                "Take a stance. Be specific. Be direct. Do not hedge with 'it depends'. "
                "The best creator reviews make readers either violently agree or want to debate you."
            ),
            item_instruction=(
                f"Each slot must evaluate ONE distinct, specific aspect of '{topic}' "
                "and deliver a clear, defensible verdict on that aspect. "
                "Do NOT repeat the same angle across slots. "
                "Each slot must feel like a standalone, shareable opinion post."
            ),
            title_guide=(
                "A specific, opinion-forward headline that states the verdict or a provocative claim. "
                "Patterns: '[Tool/Concept] is overrated. Here is why:' / "
                "'I tried [X] for [time]. Here is my honest verdict:' / "
                "'Why [X] beats [Y] for [specific use case] -- no contest.'"
            ),
            hook_guide=(
                "A bold, opinionated 1-2 sentence opener that states the verdict upfront. "
                "Do NOT tease. Do NOT delay. Open with the conclusion. "
                "Pattern: 'Hot take: [X] is the most overrated tool in [space]. Here is the evidence:' / "
                "'I have used [X] for [time] and my honest verdict is [clear position]:' / "
                "'Everyone recommends [X]. I disagree. Here is why:'"
            ),
            summary_guide=(
                '["What it does / claims to do: One tight objective description", '
                '"The honest verdict: Bold, specific, one-line opinion -- good, bad, or nuanced with a clear lean", '
                '"Who it is actually for (and who should skip it): Specific audience fit statement"]'
            ),
            link_guide=(
                "MUST be a real URL from the source data if this slot is based on a specific source. "
                "Use empty string \"\" only for general opinions not tied to one source. "
                "Never invent a URL."
            ),
            caption_guide=(
                "Write a bold, creator-voice opinion caption in 4 sections:\n"
                "1) VERDICT FIRST (2 lines): State your position clearly and confidently. No hedging.\n"
                "2) THE EVIDENCE (3-4 bullets): Specific reasons backing the verdict. "
                "Source-backed where possible. Bold emoji anchors.\n"
                "3) STEELMAN (1-2 lines): Acknowledge the strongest counterargument briefly, "
                "then hold your ground: 'Yes, [counterpoint] -- but here is why that does not change the verdict:'\n"
                "4) CTA: 'Agree or disagree? Drop your take below.' or 'Save this before you make a decision on [X].'\n"
                "Hard line breaks between sections. No corporate neutrality. "
                "Write like a creator with a reputation to defend. Never put hashtags in the caption."
            ),
        )
