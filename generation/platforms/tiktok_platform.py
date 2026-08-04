from generation.platforms.base_platform import BasePlatformStrategy


class TikTokPlatform(BasePlatformStrategy):
    name = "tiktok"

    def structure_note(self) -> str:
        return "Each slot is a short-form VIDEO SCRIPT (scene-by-scene beats), not a static image caption."

    def wrap_caption_guide(self, base_caption_guide: str) -> str:
        return (
            "A scene-by-scene short-video script (3-5 beats, each beat one line: what's shown + what's said), "
            "fast-paced, raw/authentic tone, ending on a strong pattern-interrupt CTA. Do not write this as a "
            "static image caption."
        )