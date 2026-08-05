"""generation/platforms/base_platform.py -- Platform Strategy interface.

Each concrete strategy owns "how to package it" for one platform, entirely
independent of intent -- must never branch on state["content_intent"].
"""
from abc import ABC, abstractmethod


class BasePlatformStrategy(ABC):
    name: str = "base"

    def tone_settings(self) -> dict:
        # config.PLATFORM_SETTINGS stays the single source of truth for
        # max_caption_chars/hashtag_count (workflow/gates.py's validation
        # already reads from there) -- this layer doesn't duplicate it,
        # only adds structural behavior config.py has no place for.
        from Config.config import PLATFORM_SETTINGS
        return PLATFORM_SETTINGS.get(self.name, PLATFORM_SETTINGS["instagram"])

    def effective_post_count(self, requested_count: int) -> int:
        """Override to force a fixed slot count (e.g. LinkedIn: always 1)."""
        return requested_count

    @abstractmethod
    def structure_note(self) -> str:
        """One sentence describing this platform's output SHAPE."""
        raise NotImplementedError

    def wrap_caption_guide(self, base_caption_guide: str) -> str:
        """Override to reshape the intent strategy's caption_guide for
        this platform's format. Default: pass it through unchanged."""
        return base_caption_guide