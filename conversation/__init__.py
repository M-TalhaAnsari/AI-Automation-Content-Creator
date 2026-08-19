"""
conversation/ -- Public interface
===================================
Turn-by-turn conversation management: intent routing and action execution.

Usage:
    from conversation import process_turn, maybe_summarize, update_last_tool_result
    from conversation import edit_existing, add_constraint, remove_constraint

What lives here:
    orchestrator.py -- process_turn(), maybe_summarize(), update_last_tool_result()
                      Uses Groq tool-calling to decide which action to dispatch.
    actions.py      -- edit_existing(), add_constraint(), remove_constraint(), targeted_refetch()
                      Pure action implementations, no LLM routing logic here.
"""
from orchestration.conversation_agent import process_turn, maybe_summarize, update_last_tool_result
from conversation.actions import edit_existing, add_constraint, remove_constraint, targeted_refetch