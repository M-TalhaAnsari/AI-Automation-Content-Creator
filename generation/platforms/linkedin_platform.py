from generation.platforms.base_platform import BasePlatformStrategy


class LinkedInPlatform(BasePlatformStrategy):
    name = "linkedin"
    DEFAULT_POST_COUNT = 1

    def accumulates_posts(self) -> bool:
        return False

    def structure_note(self) -> str:
        return (
            "ONE consolidated long-form thought-leadership post, not a multi-post carousel — "
            "professional insight over promotional carousel framing, minimal hashtags."
        )

    def wrap_caption_guide(self, base_caption_guide: str) -> str:
        return (
            base_caption_guide
            + " Write as a single cohesive LinkedIn post (not a slide/slot excerpt) — "
              "professional register, no comment-bait CTA, end with a genuine discussion question."
        )