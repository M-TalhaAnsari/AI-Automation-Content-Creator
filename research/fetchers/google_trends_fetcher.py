"""
fetchers/google_trends_fetcher.py — Google Trends Autocomplete Fetcher

Uses Google's public Autocomplete endpoint to get topic-relevant search
suggestions. The RSS "daily trending searches" endpoint was deliberately
removed — it returns globally trending topics (e.g. "Taylor Swift",
"World Cup") completely unrelated to the user's actual topic, which
was polluting content generation with irrelevant context. Autocomplete
suggestions are topic-specific and therefore the only reliable signal
this source provides.
"""

from typing import List, Dict, Any
from .base import logger, normalize_item
import requests
import xml.etree.ElementTree as ET


def fetch_autocomplete_suggestions(query: str) -> List[str]:
    """Fetch Google Autocomplete suggestions for a topic."""
    if not query:
        return []
    try:
        url = "http://suggestqueries.google.com/complete/search"
        params = {"output": "toolbar", "q": query}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        suggestions = [
            s.attrib["data"] for s in root.findall(".//suggestion") if s.attrib.get("data")
        ]
        logger.info(f"Fetched {len(suggestions)} autocomplete suggestions for '{query}'")
        return suggestions
    except Exception as e:
        logger.error(f"Failed to fetch autocomplete suggestions: {e}")
        return []


def fetch_google_trends(state, config) -> List[Dict[str, Any]]:
    """
    Returns topic-specific autocomplete suggestions as fetch items.
    Returns an empty list if no topic is available — this source has
    nothing useful to contribute without a topic to search around.
    """
    topic = getattr(state, "core_topic", "")
    items: List[Dict[str, Any]] = []

    if not topic:
        logger.info("No topic provided; skipping Google Trends.")
        return items

    suggestions = fetch_autocomplete_suggestions(topic)
    for suggestion in suggestions[:10]:
        items.append(normalize_item(
            title=suggestion,
            link=f"https://www.google.com/search?q={suggestion.replace(' ', '+')}",
            summary=f"Suggested search: {suggestion}",
            source="google_autocomplete",
        ))

    logger.info(f"Returning {len(items)} Google Trends autocomplete items.")
    return items