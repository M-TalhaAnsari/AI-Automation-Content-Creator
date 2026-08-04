from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class InspireIntent(BaseIntentStrategy):
    name = "inspire"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        return IntentGuidance(
            intent_instruction=(
                "The user wants MOTIVATIONAL/INSPIRATIONAL content built around the topic. "
                "Use the fetched source data as supporting evidence or real-world proof points, but the emotional "
                "angle — not the raw facts — is the actual content. Make it feel personal and human, not corporate."
            ),
            item_instruction=(
                f"Each slot must hit ONE distinct emotional angle or takeaway related to '{topic}' "
                "(e.g. overcoming a specific obstacle, a mindset shift, a concrete transformation). "
                "Avoid repeating the same emotional beat across multiple slots."
            ),
            title_guide="Short, emotionally resonant phrase capturing the core message of this slot",
            hook_guide="An opening line that creates an immediate emotional connection — vulnerability, relatability, or a bold truth",
            summary_guide='["The struggle or starting point", "The shift or insight", "The takeaway for the reader"]',
            link_guide=(
                'OPTIONAL — a real URL from the source data above may support this slot as proof, but is not required. '
                'Use empty string "" if nothing maps cleanly. Never invent a URL.'
            ),
            caption_guide=(
                "Write in a warm, first-person, human voice — not a corporate tone. Tell a short story or make a "
                "direct, honest point tied to the emotional angle for this slot. End with a genuine question or "
                "call-to-reflection that invites the audience to share their own experience, not a repo/download CTA."
            ),
        )