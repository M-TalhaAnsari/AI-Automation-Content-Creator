"""
research/ -- Public interface
===================================
All data fetching and source routing lives here.
Nothing outside this module should import from research/fetchers/* directly.

Usage:
    from research import FetcherOrchestrator, RouterOrchestrator

What lives here:
    fetchers/             -- One fetcher per source (github, reddit, tavily, etc.)
    routing/              -- RuleRouter, LLMRouter, RouterOrchestrator, registry
"""
from research.fetchers.fetcher_orchestrator import FetcherOrchestrator
from research.routing.router_orchestrator import RouterOrchestrator