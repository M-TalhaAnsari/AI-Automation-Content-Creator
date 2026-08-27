from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class ShowcaseIntent(BaseIntentStrategy):
    name = "showcase"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        data_starved = state.get("data_starved", False)

        if data_starved:
            intent_instruction = (
                "The user wants to showcase compelling project ideas or concepts related to the topic. "
                "Frame them as exciting builds to inspire developers."
            )
            item_instruction = "Each slot pitches one distinct project idea with minimal on-screen text and a rich caption."
            link_guide = '""'
            caption_guide = (
                "Engaging project concept breakdown written in natural capitalization (no all-caps headers). "
                "Includes concept summary, suggested stack, practical application, and an engagement question."
            )
        else:
            intent_instruction = (
                "The user wants to showcase real, portfolio-grade project implementations. "
                "Write high-converting, curiosity-driven copy that highlights what makes the project special."
            )
            item_instruction = "Each slot showcases one real implementation with a short on-screen graphic card and a rich caption."
            link_guide = "Valid URL from the source data."
            caption_guide = (
                "Engaging project breakdown written in natural capitalization (no all-caps headers). "
                "Details what it does, the tech stack, key features, and a comment CTA to receive the link. "
                "Format in bullet points or short paragraphs matching user prompt preferences."
            )

        return IntentGuidance(
            intent_instruction=intent_instruction,
            item_instruction=item_instruction,
            title_guide=f"Compelling real-world project name built with {topic}",
            hook_guide="One-line hook highlighting the main achievement or capability",
            summary_guide='["1. Core tech stack", "2. Standout feature", "3. Real-world impact"]',
            link_guide=link_guide,
            caption_guide=caption_guide,
        )
