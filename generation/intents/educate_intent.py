from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class EducateIntent(BaseIntentStrategy):
    name = "educate"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        return IntentGuidance(
            intent_instruction=(
                "The user wants high-value EDUCATIONAL content that breaks down core concepts of the topic clearly, "
                "for a general audience interested in the subject. "
                "Do NOT write project blueprints or instruct people to download a code repository. "
                "Use your deep knowledge base to explain the mechanics, principles, or reasoning behind the subject. "
                "Use the fetched source data as modern context, real-world proof, or baseline references. "
                "Only frame this around interviews, exams, or professional certification if the user's raw request "
                "explicitly asks for that (see CORE INSTRUCTIONS below) — otherwise explain the topic on its own "
                "terms, whatever domain it's in (technical, lifestyle, business, etc.)."
            ),
            item_instruction=(
                f"Each of the generated slots must teach ONE distinct, foundational concept of '{topic}' "
                "independently — for a technical topic, distinct mechanisms or components (e.g., if Docker: "
                "Images vs Containers, Storage Volumes, Network Isolation); for a non-technical topic, distinct "
                "principles, techniques, or steps relevant to that subject."
            ),
            title_guide="Clean, high-impact concept name relevant to the topic's own domain — not necessarily technical (e.g., 'How Docker Isolation Actually Works' for a tech topic, or 'Why Morning Light Resets Your Cortisol' for a lifestyle topic)",
            hook_guide="A powerful, authority-driven hook sentence establishing why this concept matters. If the user explicitly requested a specific line, theme, or framing (like interview prep) in their raw prompt, you MUST adapt and use that exact sentiment as your hook — otherwise keep the hook general-audience, not assuming any specific professional context.",
            summary_guide='["Core Sub-Concept Breakdown 1", "Underlying Mechanism or Principle 2", "Common Misconception or Pitfall 3"]',
            link_guide=(
                'OPTIONAL — include a real URL copied exactly from the source data above ONLY if one directly '
                'supports this specific concept slot. If no single source maps cleanly to this concept, use an '
                'empty string "". Never invent a URL.'
            ),
            caption_guide=(
                "Full multi-paragraph educational breakdown of this concept. Explain how it works at a systems level. "
                "Keep the language sharp, precise, and deeply technical so it reads perfectly for an engineer preparing for a technical round. "
                "End with a clear, engaging call-to-action that encourages saves or invites conceptual answers in the comments. Do not mention source code repos or downloading links."
            ),
        )