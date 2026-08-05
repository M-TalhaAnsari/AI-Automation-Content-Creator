"""
routing/base.py — Extensibility Contracts (Abstract Base Classes)

THIS IS THE MOST IMPORTANT FILE IN THE ROUTING LAYER.

Every router, every source, every future addition MUST implement
these contracts. This guarantees:

  - Adding a new source = create one class, register one line
  - Adding a new category = add one dict entry in config.py
  - Adding a new router strategy = create one class
  - Nothing else ever needs to change

Design Pattern: Strategy Pattern + Registry Pattern
- Strategy: any router can be swapped without touching the pipeline
- Registry: sources/routers register themselves, pipeline discovers them

Future engineer adding "LinkedIn Trending" source:
  1. Create fetchers/linkedin_fetcher.py
  2. class LinkedInFetcher(BaseFetcher)
  3. Register: SOURCE_REGISTRY["linkedin"] = LinkedInFetcher
  Done. Nothing else changes.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from core.state import TrendForgeState


# ═══════════════════════════════════════════════════════
# ROUTER CONTRACT
# Every routing strategy must implement this
# ═══════════════════════════════════════════════════════

class BaseRouter(ABC):
    """
    Abstract base for all source selection strategies.

    A router takes the current state (which has detected_category,
    core_topic, special_requests etc.) and returns a list of
    source names to fetch from.

    Built-in routers:
        RuleRouter   — keyword matching, 0 tokens
        LLMRouter    — LLaMA3 8B, ~100 tokens (for ambiguous cases)

    Future routers you could add:
        MLRouter     — trained classifier model
        UserRouter   — user explicitly picks sources
        CachedRouter — returns cached routing for repeated topics
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this router strategy."""
        pass

    @abstractmethod
    def can_handle(self, state: TrendForgeState) -> bool:
        """
        Returns True if this router is confident enough to handle
        the current state. If False, the orchestrator tries next router.

        Example:
            RuleRouter.can_handle() → True if keywords match
            LLMRouter.can_handle() → True always (fallback)
        """
        pass

    @abstractmethod
    def select_sources(self, state: TrendForgeState) -> List[str]:
        """
        Core method — returns list of source names to fetch from.
        Sources must exist in SOURCE_REGISTRY in registry.py.

        Args:
            state: current pipeline state with parsed intent

        Returns:
            list of source name strings e.g. ["github", "reddit"]
        """
        pass

    def validate_sources(self, sources: List[str], available: List[str]) -> List[str]:
        """
        Filters selected sources to only include available ones.
        Prevents routing to sources with missing API keys.
        Called automatically by the orchestrator.
        """
        return [s for s in sources if s in available]


# ═══════════════════════════════════════════════════════
# SOURCE METADATA CONTRACT
# Every data source must implement this
# ═══════════════════════════════════════════════════════

class SourceMetadata:
    """
    Describes a data source — what it is, what it needs, what it returns.
    Registered in SOURCE_REGISTRY so the system knows about it.

    This is NOT the fetcher itself — it is the metadata about the fetcher.
    The actual fetcher lives in fetchers/*.py

    Why separate metadata?
    - Router needs to know about sources without importing all fetchers
    - Status display uses metadata without running fetches
    - Future: auto-documentation, API discovery, source health checks
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
        categories: List[str],       # which topic categories this source fits
        requires_key: bool,
        key_env_var: Optional[str],  # which env var holds the API key
        rate_limit: str,             # human readable e.g. "60 req/hour"
        data_freshness: str,         # "real-time" | "daily" | "weekly"
        fetcher_module: str,         # module path e.g. "fetchers.github_fetcher"
        fetcher_class: str,          # class name e.g. "GitHubFetcher"
        enabled_by_default: bool = True,
    ):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.categories = categories
        self.requires_key = requires_key
        self.key_env_var = key_env_var
        self.rate_limit = rate_limit
        self.data_freshness = data_freshness
        self.fetcher_module = fetcher_module
        self.fetcher_class = fetcher_class
        self.enabled_by_default = enabled_by_default

    def __repr__(self):
        return f"<Source: {self.name} | categories={self.categories} | key={self.requires_key}>"
