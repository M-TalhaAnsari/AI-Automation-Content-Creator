"""
understanding/prompt_parser.py — Step 2 Main Orchestrator

Single entry point for the understanding layer.
Connects PromptCleaner (0 tokens) → IntentExtractor (Groq LLM call).

Any prompt — short, long, ambiguous, multilingual — goes in.
Clean structured state comes out, every time.

Architecture:
    raw_prompt
        ↓
    PromptCleaner (pure Python, 0 tokens)
    - detects platform, post count, special requests
    - strips noise from text
        ↓
    IntentExtractor (Groq, ~200-800 tokens depending on prompt complexity)
    - extracts core topic, category, content_intent
    - fills gaps the cleaner couldn't detect
    - generates search query variants
    - merges everything into state
        ↓
    Updated TrendForgeState
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import TrendForgeState, add_log
from understanding.prompt_cleaner import PromptCleaner
from understanding.intent_extractor import IntentExtractor


class PromptParser:
    """Step 2 entry point — understands any user prompt via rules + LLM."""

    def __init__(self):
        self.cleaner = PromptCleaner()
        self.extractor = IntentExtractor()

    def parse(self, state: TrendForgeState) -> TrendForgeState:
        """
        Takes raw state, returns fully understood state.
        Called from main.py as the first pipeline step.
        """
        add_log(state, f"[PromptParser] Starting — prompt length: {len(state['raw_prompt'])} chars")

        # ── PHASE 1: Rule-based cleaning (0 tokens) ─────────────
        add_log(state, "[PromptParser] Phase 1 — Rule-based extraction (0 tokens)...")
        pre_extracted = self.cleaner.clean(state["raw_prompt"])

        add_log(state, (
            f"[PromptParser] Rules found — "
            f"platform='{pre_extracted['detected_platform'] or 'not detected'}' "
            f"count={pre_extracted['detected_post_count'] or 'not detected'} "
            f"requests={pre_extracted['detected_special_requests']}"
        ))

        # ── PHASE 2: LLM extraction (fills semantic gaps) ────────
        add_log(state, "[PromptParser] Phase 2 — LLM intent extraction...")
        state = self.extractor.extract(state, pre_extracted)

        add_log(state, "[PromptParser] ✓ Parsing complete.")
        return state


# ─────────────────────────────────────────────
# STANDALONE TEST — rule-based cleaner only, no API key needed
# Run: python understanding/prompt_parser.py
# NOTE: this only exercises Phase 1 (PromptCleaner). It does not
# call the LLM, so it will not show core_topic/category/content_intent —
# those only exist after Phase 2 runs inside the real pipeline.
# ─────────────────────────────────────────────

def _test_cleaner_only():
    cleaner = PromptCleaner()

    test_prompts = [
        "discipline",
        "top 5 ML projects",
        "top ML projects for instagram",
        "I want top ML projects that grab user eyes and i want their github links as well. "
        "In instagram i will be uploading 5 different pictures for project. "
        "So give me also a engaging short summary or points of each project i am gonna write it in post",
        "morning routine habits for productivity youtube shorts",
        "top 3 startup ideas for 2026 linkedin post",
        "ramadan content",
        "I am a BS-IT student and i want to create content for my instagram page. "
        "The content should be about machine learning projects that are trending right now in 2026. "
        "I want to upload 5 separate posts each covering one ML project. "
        "Each post should have the github link, a short engaging summary with bullet points, "
        "and a viral hook that will make people stop scrolling. "
        "Please also include hashtags and a caption that i can directly paste.",
    ]

    print("\n" + "═" * 60)
    print("  PROMPT CLEANER TEST (Phase 1 only — 0 tokens, no API needed)")
    print("═" * 60)

    for prompt in test_prompts:
        result = cleaner.clean(prompt)
        print(f"\n  INPUT:      \"{prompt[:70]}{'...' if len(prompt) > 70 else ''}\"")
        print(f"  Cleaned:    \"{result['cleaned_text'][:70]}\"")
        print(f"  Platform:   {result['detected_platform'] or '(not detected)'}")
        print(f"  Count:      {result['detected_post_count'] or '(not detected)'}")
        print(f"  Requests:   {result['detected_special_requests']}")
        print(f"  Confidence: {result['extraction_confidence']}")
        print(f"  Long:       {result['is_long']} ({result['word_count']} words)")

    print("\n" + "═" * 60)
    print("  Cleaner tests complete.")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    _test_cleaner_only()