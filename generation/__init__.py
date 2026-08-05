# generation package
"""
generation/ -- Public interface
===================================
Everything outside this module that needs content generation
imports ONLY from here, never from submodules directly.

Usage:
    from generation import ContentGenerator, compose_prompt

What lives here:
    content_generator.py  -- ContentGenerator class (select intent -> select platform -> one LLM call)
    prompt_composer.py    -- compose_prompt(state) -> str  (combines both strategy hierarchies)
    prompts.py            -- legacy build_generation_prompt (kept, not deleted)
    formatter.py          -- format_output(state), save_output(state)
    intents/              -- Intent Strategy implementations + registry
    platforms/            -- Platform Strategy implementations + registry
"""
from generation.content_generator import ContentGenerator
from generation.prompt_composer import compose_prompt
from generation.formatter import format_output, save_output