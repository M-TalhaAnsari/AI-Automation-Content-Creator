"""generation/intents/registry.py -- Intent Strategy registry + dispatcher.

Pure Python dict lookup, same pattern as fetchers/fetcher_orchestrator.py's
FETCHER_MAP. Adding a new intent: create a new BaseIntentStrategy
subclass, add one line here -- nothing else changes (Open/Closed).
"""
from generation.intents.showcase_intent import ShowcaseIntent
from generation.intents.educate_intent import EducateIntent
from generation.intents.news_intent import NewsIntent
from generation.intents.inspire_intent import InspireIntent
from generation.intents.review_intent import ReviewIntent

INTENT_STRATEGY_MAP = {
    "showcase": ShowcaseIntent(),
    "educate": EducateIntent(),
    "news": NewsIntent(),
    "inspire": InspireIntent(),
    "review": ReviewIntent(),
}


def get_intent_strategy(content_intent: str):
    return INTENT_STRATEGY_MAP.get(content_intent, INTENT_STRATEGY_MAP["showcase"])