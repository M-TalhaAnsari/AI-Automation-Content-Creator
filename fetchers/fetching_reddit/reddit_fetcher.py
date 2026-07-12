"""
Reddit fetcher - Now uses the Intelligence Layer.
"""
from typing import List, Dict, Any
import logging
from .reddit_intelligence import fetch_reddit_intelligence

logger = logging.getLogger("trendforge.fetchers.reddit")

def fetch_reddit(state, config) -> List[Dict[str, Any]]:
    """
    Main Reddit fetcher - uses the Intelligence Layer.
    """
    return fetch_reddit_intelligence(state, config)