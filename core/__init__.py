# core package
"""
core/ -- Public interface
===================================
Shared infrastructure used by every other module.
Never imports from any other TrendForge module -- zero circular dependencies.

Usage:
    from core import TrendForgeState, create_initial_state
    from core import add_log, add_error, add_tokens, get_total_tokens

What lives here:
    state.py         -- TrendForgeState TypedDict + create_initial_state() + state helpers
    token_tracker.py -- TokenTracker class used by generation/formatter.py
"""
from core.state import (
    TrendForgeState,
    create_initial_state,
    add_log,
    add_error,
    add_tokens,
    get_total_tokens,
)