from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class EducateIntent(BaseIntentStrategy):
    name = "educate"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        return IntentGuidance(
            intent_instruction=(
                "The user wants HIGH-VALUE EDUCATIONAL content that drives saves and shares. "
                "You are writing for a creator account with 100K+ followers, not a textbook or lecture. "
                "Every post must teach ONE sharp concept in a way that makes the reader feel smarter in 60 seconds. "
                "Use the fetched source data as real-world proof and modern context, not as the primary frame. "
                "DO NOT write academic study guides, exam prep breakdowns, or corporate documentation. "
                "DO write punchy, high-signal, value-dense creator copy that gets saved and shared."
            ),
            item_instruction=(
                f"Each slot must teach exactly ONE distinct, actionable concept of '{topic}' "
                "that a professional creator would turn into a viral carousel slide. "
                "The concept must be teachable in 3-5 bullets and a single clear caption. "
                "Do NOT repeat concepts across slots. Each slot must feel like a standalone viral post."
            ),
            title_guide=(
                "A bold, curiosity-gap headline that makes a developer stop scrolling. "
                "Use patterns like: 'How [concept] actually works (and why everyone gets it wrong)' or "
                "'The [concept] rule every senior engineer knows' or '[Number] things about [concept] nobody tells you'. "
                "No generic labels. No academic module names."
            ),
            hook_guide=(
                "A 1-2 sentence power hook using the curiosity gap + value promise formula. "
                "MUST make the reader feel they are about to learn something they were never taught. "
                "Examples: 'Stop learning [X] the wrong way. Here is the exact framework top engineers use:' / "
                "'Most people use [X] but never understand why. Here is the part they skip:' / "
                "'[X] is not complicated. You just never saw it explained this clearly:'"
            ),
            summary_guide=(
                '["Bold Keyword: One-line punchy takeaway that delivers real insight with no fluff", '
                '"Bold Keyword: Another punchy standalone insight with a surprising or counterintuitive angle", '
                '"Bold Keyword: The most overlooked or misunderstood truth about this concept"]'
            ),
            link_guide=(
                "OPTIONAL: include a real URL copied exactly from the source data ONLY if one directly "
                "supports this specific concept slot. If no source maps cleanly, use empty string \"\". "
                "Never invent a URL."
            ),
            caption_guide=(
                "Write a visual-first, mobile-card-optimized educational caption in 4 tight sections:\n"
                "1) HOOK (2 lines max): curiosity gap that earns the scroll.\n"
                "2) THE INSIGHT (3-5 punchy bullets, each starting with an emoji + bold keyword, max 15 words per bullet).\n"
                "3) THE CONTEXT (1-2 lines): explain WHY this matters RIGHT NOW, tie to real-world impact.\n"
                "4) CTA: 'Save this. What would you add? Drop your answer below.'\n"
                "HARD RULES: No walls of text. Hard line breaks between sections. "
                "No academic language (no 'mechanism', 'underlying principle', 'sub-concept'). "
                "Write like a top creator, not a professor. Never put hashtags here."
            ),
        )
