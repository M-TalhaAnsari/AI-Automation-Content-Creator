from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class EducateIntent(BaseIntentStrategy):
    name = "educate"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        return IntentGuidance(
            intent_instruction=(
                "The user wants high-value educational content that drives organic saves and shares. "
                "Write like a top creator, breaking down complex ideas into simple, intuitive takeaways. "
                "Keep on-screen text clean and minimal (headline + 3 short points), and put the rich, "
                "detailed explanation into the caption description."
            ),
            item_instruction=(
                f"Each slot must teach one clear concept of '{topic}' with minimal on-screen text and a rich description."
            ),
            title_guide=(
                "A bold, high-impact headline (e.g. 'How Docker Isolation Actually Works' or 'The 3-Step RAG Framework')"
            ),
            hook_guide=(
                "A punchy subtitle (e.g. 'Everything you need to understand it in 60 seconds')"
            ),
            summary_guide=(
                '["1. Core principle in 6 words", "2. How it works in 6 words", "3. Pro tip in 6 words"]'
            ),
            link_guide=(
                "OPTIONAL: Real source URL if available from data, otherwise empty string \"\"."
            ),
            caption_guide=(
                "A complete, value-packed educational post caption. "
                "Write with natural capitalization (no all-caps headers). "
                "If the user requested bullet points, format using clean bullet points. "
                "Include a hook, concise explanation, practical takeaway, and save-this CTA. "
                "Never put hashtags in the caption."
            ),
        )
