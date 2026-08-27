from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class InspireIntent(BaseIntentStrategy):
    name = "inspire"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        return IntentGuidance(
            intent_instruction=(
                "The user wants MOTIVATIONAL content that hits emotionally and drives massive shares. "
                "You are not a life coach writing LinkedIn platitudes -- you are a creator who tells "
                "uncomfortable truths that resonate deeply with your audience. "
                "Use the fetched source data as real-world proof and supporting context. "
                "Write from a human, personal voice. Make the reader feel seen and fired up. "
                "DO NOT write generic corporate motivational copy. "
                "DO write honest, specific, slightly uncomfortable truths that earn saves."
            ),
            item_instruction=(
                f"Each slot must deliver ONE distinct emotional punch related to '{topic}'. "
                "Hit a specific angle: a mindset shift, a real obstacle overcome, a counterintuitive truth. "
                "Do NOT repeat the same emotional beat across slots. "
                "Every post should make the reader screenshot and share it."
            ),
            title_guide=(
                "A short, emotionally loaded headline that triggers instant recognition. "
                "Patterns: 'The [uncomfortable truth] about [topic] nobody wants to admit.' / "
                "'Why most people [fail at X] -- and the one shift that changes everything.' / "
                "'[Specific hard lesson] I learned from [topic] that took me [time] to understand.'"
            ),
            hook_guide=(
                "A 1-2 sentence opener that creates immediate emotional connection through "
                "vulnerability, a bold truth, or a relatable struggle. "
                "Pattern: 'I spent [time] getting [X] wrong. Here is the truth I finally accepted:' / "
                "'The most successful people I know do not [common belief]. They do this instead:' / "
                "'Nobody tells you how hard [X] is before you start. So I will:'"
            ),
            summary_guide=(
                '["The struggle: The honest, specific starting point most people recognize", '
                '"The shift: The insight, decision, or reframe that changed everything", '
                '"The takeaway: What the reader can apply TODAY, stated as a direct, personal challenge"]'
            ),
            link_guide=(
                "OPTIONAL: a real URL from the source data may support this slot as proof. "
                "Use empty string \"\" if nothing maps cleanly. Never invent a URL."
            ),
            caption_guide=(
                "Write a warm, human, first-person inspirational caption in 4 sections:\n"
                "1) HOOK (2 lines): A bold truth or relatable struggle that makes the reader stop.\n"
                "2) THE STORY (3-4 punchy lines): What happened, what was learned, what shifted. "
                "Specific details. Not vague affirmations.\n"
                "3) THE TAKEAWAY (1-2 lines): Direct, personal, actionable. "
                "'Start [X]. Stop [Y]. Do [Z] today.'\n"
                "4) CTA: 'Save this for when you need it. What would you add?' or "
                "'Tag someone who needs to hear this.'\n"
                "Hard line breaks between sections. No corporate tone. No generic platitudes. "
                "Write like a real human, not a motivational poster. Never put hashtags in the caption."
            ),
        )
