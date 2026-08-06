"""generation/platforms/base_platform.py -- Platform Strategy interface.

Each concrete strategy owns "how to package it" for one platform, entirely
independent of intent -- must never branch on state["content_intent"].
"""
from abc import ABC, abstractmethod


class BasePlatformStrategy(ABC):
    name: str = "base"

    # Override to set this platform's default slot count for when the
    # user did NOT explicitly ask for a specific number (None = just use
    # whatever the pipeline already resolved, usually 5).
    DEFAULT_POST_COUNT = None

    def tone_settings(self) -> dict:
        from Config.config import PLATFORM_SETTINGS
        return PLATFORM_SETTINGS.get(self.name, PLATFORM_SETTINGS["instagram"])

    def effective_post_count(self, requested_count: int, is_explicit: bool = True) -> int:
        """Returns the actual number of post slots to generate.

        is_explicit=True: the user actually asked for `requested_count`
        (or it's already a deliberate value, e.g. generate_more's count
        arg) -- always honored, regardless of platform.

        is_explicit=False: requested_count is just the pipeline's generic
        fallback (usually 5, understanding/intent_extractor.py's default
        when no number was detected in the user's text) -- this platform's
        own DEFAULT_POST_COUNT is used instead, if it has one.
        """
        if is_explicit or self.DEFAULT_POST_COUNT is None:
            return requested_count
        return self.DEFAULT_POST_COUNT

    @abstractmethod
    def structure_note(self) -> str:
        """One sentence describing this platform's output SHAPE."""
        raise NotImplementedError

    def wrap_caption_guide(self, base_caption_guide: str) -> str:
        """Override to reshape the intent strategy's caption_guide for
        this platform's format. Default: pass it through unchanged."""
        return base_caption_guide

    def accumulates_posts(self) -> bool:
        """Whether "generate more on the same topic" should ADD to the
        existing posts array (True, the norm -- Instagram, TikTok,
        YouTube, Facebook) or replace it because this platform's format
        is one consolidated piece, not a growable series (False --
        LinkedIn)."""
        return True

    def repeat_request_note(self) -> str:
        """One sentence describing this platform's behavior when the
        user asks for more content on the same topic. Read by
        conversation/orchestrator.py -- kept here, not hardcoded per
        platform name in a shared file, so each platform's behavior is
        defined exactly once, in the one place that owns it."""
        if self.accumulates_posts():
            return "Additional requests on the same topic ADD new posts to the existing series."
        return (
            "This platform produces ONE consolidated post -- a repeat request replaces it "
            "entirely, it does not create a second post."
        )