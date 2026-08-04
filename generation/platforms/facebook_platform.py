from generation.platforms.base_platform import BasePlatformStrategy


class FacebookPlatform(BasePlatformStrategy):
    name = "facebook"

    def structure_note(self) -> str:
        return (
            "A single community-oriented post per slot — conversational, shareable, discussion-inviting, "
            "not portfolio/comment-bait framing."
        )