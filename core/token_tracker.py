"""
core/token_tracker.py — Token Usage Reporting

Generates the final token usage report shown at the end of every run.
Token counts themselves are recorded via add_tokens() in core/state.py —
this file only READS state["tokens"] to build a human-readable report
and cost estimate. It does not record tokens itself.
"""

from core.state import TrendForgeState, get_total_tokens
from config import CONFIG


# Cost per 1M tokens (USD, approximate) — keys MUST match the actual
# model identifiers configured in config.py, or cost lookup silently
# falls back to the default rate below.
COST_PER_MILLION_TOKENS = {
    "openai/gpt-oss-20b":      0.05,
    "openai/gpt-oss-120b":     0.59,
    "gemini-2.0-flash":        0.10,
    "llama-3.3-70b-versatile": 0.59,   # Groq fallback model used by content_generator.py
}

DEFAULT_RATE_PER_MILLION = 0.10   # used when a model isn't in the table above


class TokenTracker:
    """
    Reads state["tokens"] and produces the final formatted report.
    Recording tokens happens elsewhere (add_tokens in state.py) —
    this class is read-only / reporting-only by design.
    """

    def __init__(self, state: TrendForgeState):
        self.state = state

    def calculate_cost(self, tokens: int, model: str) -> float:
        """Estimates cost in USD for a given token count and model."""
        rate = COST_PER_MILLION_TOKENS.get(model, DEFAULT_RATE_PER_MILLION)
        return (tokens / 1_000_000) * rate

    def _content_generation_model(self) -> str:
        """
        content_generation tokens can come from either engine depending on
        whether Gemini succeeded or the Groq fallback ran (see
        content_generator.py). Price using whichever one actually served
        this run instead of always assuming Gemini.
        """
        engine = self.state.get("content_generation_engine", "")
        if "groq" in engine.lower():
            return CONFIG.models.groq_model_large
        return CONFIG.models.gemini_model

    def generate_report(self, sources_used: list = None, models_used: list = None) -> str:
        """Builds the final token usage report string shown at the end of every run."""
        tokens = self.state["tokens"]
        total = get_total_tokens(self.state)

        gen_model = self._content_generation_model()

        parsing_cost = self.calculate_cost(tokens.get("prompt_parsing", 0), CONFIG.models.groq_model_small)
        routing_cost = self.calculate_cost(tokens.get("source_routing", 0), CONFIG.models.groq_model_small)
        gen_cost = self.calculate_cost(tokens.get("content_generation", 0), gen_model)
        total_cost = parsing_cost + routing_cost + gen_cost

        sources_str = ", ".join(sources_used) if sources_used else "none"
        models_str = ", ".join(models_used) if models_used else "Groq + Gemini"

        return f"""
                {'═' * 52}
                TOKEN USAGE REPORT
                {'═' * 52}
                Prompt parsing:      {tokens.get('prompt_parsing', 0):>6} tokens  (Groq — {CONFIG.models.groq_model_small})
                Source routing:      {tokens.get('source_routing', 0):>6} tokens  (rules + Groq fallback)
                Data fetching:       {tokens.get('data_fetching', 0):>6} tokens  (HTTP APIs — free)
                Content generation:  {tokens.get('content_generation', 0):>6} tokens  ({gen_model})
                {'─' * 48}
                TOTAL:               {total:>6} tokens
                ESTIMATED COST:      ${total_cost:.4f} USD
                {'─' * 48}
                Models used:    {models_str}
                Sources used:   {sources_str}
                {'═' * 52}""".strip()