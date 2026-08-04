from generation.platforms.base_platform import BasePlatformStrategy


class InstagramPlatform(BasePlatformStrategy):
    name = "instagram"

    def structure_note(self) -> str:
        return "A multi-post carousel series — each slot is one standalone, scrollable image-caption post."