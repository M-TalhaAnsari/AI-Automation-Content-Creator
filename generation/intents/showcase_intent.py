from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class ShowcaseIntent(BaseIntentStrategy):
    name = "showcase"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        data_starved = state.get("data_starved", False)

        if data_starved:
            intent_instruction = (
                "The user wants to showcase compelling PROJECT CONCEPTS related to the topic, but the fetched "
                "source data was insufficient or low-quality even after retries — treat these as original concept "
                "pitches drawn from your own knowledge, NOT as descriptions of a specific existing repository. "
                "Do not imply a real, ready-made codebase exists to hand over."
            )
            item_instruction = (
                "Each slot must pitch ONE distinct, plausible project concept. End each caption with a genuine "
                "engagement question or a 'would you build this?' style prompt — NOT a 'comment X and I'll DM "
                "you the repo' CTA, since no real repository exists behind this concept."
            )
            link_guide = 'Leave as an empty string "" — there is no real source to link to. Never invent a URL.'
            caption_guide = (
                "Full multi-paragraph caption structured with: Concept Overview, Suggested Tech Stack, and how it "
                "could work — framed clearly as an idea/concept, not a real existing project. End with a genuine "
                "question inviting engagement, not a fake repo-DM CTA."
            )
        else:
            intent_instruction = (
                "The user wants to showcase epic, actionable, portfolio-grade project implementations designed to drive high engagement. "
                "Do NOT write generic tool overviews. Turn the source data into a concrete project build blueprint."
            )
            item_instruction = (
                "Each slot must focus entirely on ONE individual project implementation. Every single caption must end with a highly "
                "specific comment-bait CTA forcing engineers to comment a keyword to receive the repository link in their DMs."
            )
            link_guide = "MUST be a real URL copied exactly from the source data above — if you describe a GitHub project, this MUST be a valid github.com URL from the sources. Never invented."
            caption_guide = (
                "Full multi-paragraph caption structured with: Project Overview, Tech Stack breakdown, Core System Architecture, "
                "and a high-conversion Call-To-Action explicitly inviting users to comment a key word to get the GitHub link auto-sent to their DMs. Do not output hashtags here."
            )

        return IntentGuidance(
            intent_instruction=intent_instruction,
            item_instruction=item_instruction,
            title_guide=f"Highly compelling, specific real-world project name built using {topic}",
            hook_guide="Disruptive, curiosity-spiking hook sentence that grabs a developer's attention instantly",
            summary_guide='["Core Technical Highlight 1", "Key System Asset 2", "Deployment Target 3"]',
            link_guide=link_guide,
            caption_guide=caption_guide,
        )