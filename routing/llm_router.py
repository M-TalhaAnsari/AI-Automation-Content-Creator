"""
routing/llm_router.py — LLM-Based Source Router (~50-100 tokens)

Used as a fallback when RuleRouter cannot confidently decide
(i.e. category came back as "unknown"). Uses Groq's small model —
fast and cheap, since this is just a classification/selection task,
not a creative one.
"""

import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from routing.base import BaseRouter
from routing.registry import get_available_sources
from core.state import TrendForgeState, add_log, add_error, add_tokens
from config import CONFIG

ROUTER_SYSTEM = "You are a source selector. Return ONLY a JSON array of source names. No explanation."


def _build_prompt(state: TrendForgeState, available: List[str]) -> str:
    return f"""Topic: "{state['core_topic']}"
Category: {state['detected_category']}
Special requests: {state['special_requests']}
Available sources: {available}

Rules:
- github, paperswithcode, huggingface → only for tech/ML/AI topics
- google_trends, reddit → work for ANY topic
- youtube → lifestyle, entertainment, education
- tavily → fallback, use when topic is niche or unusual
- Max 4 sources
- Always include google_trends for non-tech topics

Return JSON array only. Example: ["github", "reddit", "google_trends"]"""


class LLMRouter(BaseRouter):

    @property
    def name(self) -> str:
        return "llm"

    def can_handle(self, state: TrendForgeState) -> bool:
        return bool(CONFIG.models.groq_api_key)

    def select_sources(self, state: TrendForgeState) -> List[str]:
        available = get_available_sources()
        add_log(state, f"[LLMRouter] Calling Groq ({CONFIG.models.groq_model_small}) for source selection...")

        try:
            from groq import Groq
            client = Groq(api_key=CONFIG.models.groq_api_key)
            response = client.chat.completions.create(
                model=CONFIG.models.groq_model_small,
                temperature=0.1,
                max_tokens=60,
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM},
                    {"role": "user", "content": _build_prompt(state, available)},
                ]
            )
            tokens = response.usage.total_tokens
            add_tokens(state, "source_routing", tokens)
            add_log(state, f"[LLMRouter] Source selection call used {tokens} tokens")

            raw = response.choices[0].message.content.strip()
            match = re.search(r'\[.*?\]', raw, re.DOTALL)
            if match:
                sources = json.loads(match.group())
                selected = self.validate_sources(sources, available)
                if selected:
                    add_log(state, f"[LLMRouter] Selected: {selected}")
                    return selected

        except Exception as e:
            add_error(state, f"[LLMRouter] Failed: {e} — using fallback")

        fallback = self.validate_sources(["google_trends", "reddit", "tavily"], available)
        add_log(state, f"[LLMRouter] Using fallback sources: {fallback}")
        return fallback