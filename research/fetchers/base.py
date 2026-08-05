"""
base.py — Common utilities for all fetchers.

Provides:
  - safe_request: HTTP with retries and timeout
  - normalize_item: standardizes fetched data into a consistent format
  - logger: shared logging instance
"""
import logging
import time
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger("trendforge.fetchers")


def safe_request(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
    retries: int = 2,
    backoff: float = 1.0,
) -> Optional[requests.Response]:
    """
    Make an HTTP request with retries and timeout.
    Returns Response object on success, None on failure.
    """
    for attempt in range(retries + 1):
        try:
            resp = requests.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                json=json,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed (attempt {attempt+1}/{retries+1}): {e}")
            if attempt < retries:
                sleep_time = backoff * (2 ** attempt)
                time.sleep(sleep_time)
            else:
                logger.error(f"All retries exhausted for {url}")
                return None
    return None


def normalize_item(
    title: str,
    link: str,
    summary: str,
    source: str,
    **extra
) -> Dict[str, Any]:
    """
    Return a standardized item dict for all fetchers.
    Every fetcher should call this to ensure consistent fields.
    """
    return {
        "title": title.strip(),
        "link": link.strip(),
        "summary": summary.strip(),
        "source": source,
        **extra,
    }