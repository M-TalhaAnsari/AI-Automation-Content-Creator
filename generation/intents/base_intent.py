"""generation/intents/base_intent.py -- Intent Strategy interface.

Each concrete strategy owns "what to say" for one content_intent value,
entirely independent of platform -- must never branch on state["platform"].
Adding a new intent: create one new file implementing this interface, add
one line to registry.py. Nothing existing needs to change (Open/Closed).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class IntentGuidance:
    intent_instruction: str
    item_instruction: str
    title_guide: str
    hook_guide: str
    summary_guide: str
    link_guide: str
    caption_guide: str


class BaseIntentStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def get_guidance(self, state: dict) -> IntentGuidance:
        raise NotImplementedError