from generation.platforms.base_platform import BasePlatformStrategy


class LinkedInPlatform(BasePlatformStrategy):
    name = "linkedin"

    def effective_post_count(self, requested_count: int) -> int:
        # LinkedIn's format is one consolidated thought-leadership post,
        # not a carousel -- regardless of how many posts the user asked
        # for, since that request was made without platform context.
        return 1

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