from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class ReviewIntent(BaseIntentStrategy):
    name = "review"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        return IntentGuidance(
            intent_instruction=(
                "The user wants an honest OPINION or REVIEW of the topic. "
                "Take a clear, specific stance — do not hedge into a neutral summary. Use the fetched source data "
                "as evidence for your position, but the point of view itself is the content."
            ),
            item_instruction=(
                f"Each slot must cover ONE distinct aspect being evaluated about '{topic}' "
                "(e.g. one specific feature, one comparison point, one tradeoff) with a clear verdict on that aspect. "
                "Do not repeat the same evaluation angle across slots."
            ),
            title_guide="Specific aspect being reviewed in this slot, phrased with a clear point of view",
            hook_guide="A bold, opinionated opening line that states the verdict or a strong claim upfront",
            summary_guide='["What this aspect does / claims to do", "The honest verdict — good or bad", "Who this is actually good for (or not)"]',
            link_guide=(
                "MUST be a real URL copied exactly from the source data above if this slot's evaluation is based on "
                'a specific source. Empty string "" only if the point is a general opinion not tied to one source.'
            ),
            caption_guide=(
                "State your verdict clearly and early — don't bury the opinion. Back it up with specific evidence "
                "from the source data. Acknowledge the strongest counterargument briefly, then restate your position. "
                "End with a direct question asking whether the audience agrees or disagrees, not a repo/download CTA."
            ),
        )