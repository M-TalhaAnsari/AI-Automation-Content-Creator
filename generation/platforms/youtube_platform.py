from generation.platforms.base_platform import BasePlatformStrategy


class YouTubePlatform(BasePlatformStrategy):
    name = "youtube"

    def structure_note(self) -> str:
        return "Each slot is a YOUTUBE SHORTS/VIDEO SCRIPT outline, not a static image caption."

    def wrap_caption_guide(self, base_caption_guide: str) -> str:
        return (
            "A structured video script outline: opening hook line, 2-3 body beats explaining the concept, "
            "closing line with a subscribe/comment CTA. Written to be read aloud on camera, not posted as a caption."
        )