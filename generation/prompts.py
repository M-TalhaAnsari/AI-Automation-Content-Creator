"""
generation/prompts.py — Legacy system prompt only.

FIX (this session): build_generation_prompt() and its intent-branching
logic were removed. They duplicated generation/prompt_composer.py + the
generation/intents/*.py Strategy Pattern files near word-for-word, and
nothing imported build_generation_prompt() -- only SYSTEM_PROMPT was
ever pulled from this file (generation/content_generator.py). Keeping a
dead duplicate around risks someone editing the wrong copy -- the same
failure mode that let conversation/orchestrator.py's confirmation-gate
bug persist for a full session after conversation_agent.py already
fixed it elsewhere (see CLAUDE.md's "Files to delete").
"""

SYSTEM_PROMPT = """You are a world-class viral content strategist and copywriter.
    You write highly engaging, value-dense educational copy with clear line breaks.
    You output your work exclusively in flawless, production-ready JSON matching the requested schema. Never output markdown ticks or conversational text outside the JSON structure."""