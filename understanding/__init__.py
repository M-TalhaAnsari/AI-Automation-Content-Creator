# understanding package
"""
understanding/ -- Public interface
===================================
Converts raw user text into a structured state dict.

Usage:
    from understanding import PromptParser

What lives here:
    prompt_parser.py      -- PromptParser (entry point -- calls cleaner then extractor)
    prompt_cleaner.py     -- Rule-based cleaning, 0 tokens
    intent_extractor.py   -- LLM-powered intent extraction (Groq)
"""
from understanding.prompt_parser import PromptParser