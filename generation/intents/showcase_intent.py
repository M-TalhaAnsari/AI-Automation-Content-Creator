from generation.intents.base_intent import BaseIntentStrategy, IntentGuidance


class ShowcaseIntent(BaseIntentStrategy):
    name = "showcase"

    def get_guidance(self, state: dict) -> IntentGuidance:
        topic = state.get("core_topic", "")
        data_starved = state.get("data_starved", False)

        if data_starved:
            intent_instruction = (
                "The user wants to showcase compelling PROJECT CONCEPTS, but the fetched data was insufficient. "
                "Treat these as original concept pitches from your knowledge base. "
                "Write like a creator pitching ideas to a dev audience -- not describing an existing repo. "
                "Every post must make the reader think: 'I want to build this.'"
            )
            item_instruction = (
                "Each slot must pitch ONE distinct, plausible, exciting project concept. "
                "Lead with the value and outcome, not the tech stack. "
                "End each caption with a genuine engagement hook: 'Would you build this? Comment below.' "
                "Do NOT use 'comment X and I will DM you the repo' -- no real repo exists."
            )
            link_guide = "Leave as empty string \"\" -- no real source to link to. Never invent a URL."
            caption_guide = (
                "Write a 4-section creator-first project pitch caption:\n"
                "1) HOOK (2 lines): What does this project do and why is it insane?\n"
                "2) THE BUILD (3-4 bullets): Key features, smart design decisions, what makes it different.\n"
                "3) TECH STACK (1 tight line): 'Built with: [X, Y, Z]'\n"
                "4) ENGAGEMENT CTA: 'Would you build this? What would you add? Comment below.'\n"
                "Hard line breaks between sections. No walls of text. Never include hashtags here."
            )
        else:
            intent_instruction = (
                "The user wants to showcase epic, portfolio-grade, real-world project implementations. "
                "You are a top creator whose dev project posts routinely hit 500K+ impressions. "
                "Write DM-bait, save-worthy posts that make engineers stop scrolling and comment immediately. "
                "Every caption MUST end with a specific keyword CTA to receive the GitHub link in DMs."
            )
            item_instruction = (
                "Each slot MUST focus entirely on ONE individual project implementation from the source data. "
                "Lead with the impact and outcome, not generic tool descriptions. "
                "Every caption MUST end with a high-conversion comment-bait CTA: "
                "'Comment [KEYWORD] and I will DM you the full repo link.'"
            )
            link_guide = (
                "MUST be a real URL copied exactly from the source data above. "
                "If you describe a GitHub project, this MUST be a valid github.com URL from the sources. "
                "Never invent a URL."
            )
            caption_guide = (
                "Write a 4-section high-conversion project showcase caption:\n"
                "1) HOOK (2 lines max): One bold claim about what this project can do that shocks a developer.\n"
                "2) PROJECT BREAKDOWN (4-5 punchy bullets with emoji anchors): "
                "Tech stack, architecture, the most impressive feature, performance stat or real-world use case.\n"
                "3) WHO NEEDS THIS (1-2 lines): Make the reader see themselves using it.\n"
                "4) CTA: 'Comment [KEYWORD] below and I will DM you the full GitHub repo instantly.'\n"
                "Hard line breaks between sections. No walls of text. Never include hashtags here."
            )

        return IntentGuidance(
            intent_instruction=intent_instruction,
            item_instruction=item_instruction,
            title_guide=(
                f"A compelling, specific real-world project name built using {topic}. "
                "Make it sound like something a senior engineer would actually ship, not a tutorial project."
            ),
            hook_guide=(
                "A disruptive 1-2 sentence hook that creates instant curiosity and urgency. "
                "Patterns: 'This [X] project replaced [entire expensive system] in [time].' / "
                "'I built [X] in a weekend. Here is why every [role] needs it:' / "
                "'Stop using [old approach]. I built a [better solution] with [topic] that does [outcome]:'"
            ),
            summary_guide=(
                '["Core Technical Highlight: The most impressive thing about this project", '
                '"Key System Asset: The architecture or design decision that makes it scalable", '
                '"Deployment Target: Where this runs and what real-world problem it solves"]'
            ),
            link_guide=link_guide,
            caption_guide=caption_guide,
        )
