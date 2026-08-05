"""
SearXNG Search API integration for finding Reddit URLs.
Self-hosted, privacy-focused search engine.
"""
import requests
import logging
import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

logger = logging.getLogger("trendforge.fetchers.searxng")

# SearXNG endpoint (default for local Docker instance)
SEARXNG_URL = "http://localhost:8080/search"


def search_reddit(
    query: str,
    searxng_url: str = SEARXNG_URL,
    count: int = 20,
    timeout: int = 15
) -> List[Dict[str, Any]]:
    """
    Search Reddit using SearXNG with proper headers.
    """
    if not searxng_url:
        logger.error("SearXNG URL not provided.")
        return []
    
    # Build SearXNG JSON API request
    params = {
        "q": query,
        "format": "json",
        "categories": "general",
        "language": "en",
        "safesearch": 0,
        "theme": "simple",
    }
    
    # Critical: Proper headers to avoid 403
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": searxng_url,
        "Origin": searxng_url.replace("/search", ""),
        "Connection": "keep-alive",
    }
    
    try:
        # Make request to SearXNG
        response = requests.get(
            searxng_url,
            params=params,
            headers=headers,
            timeout=timeout
        )
        
        if response.status_code != 200:
            logger.error(f"SearXNG search failed with status: {response.status_code}")
            logger.debug(f"Response: {response.text[:200]}")
            
            # Check if it's a 403 and provide helpful message
            if response.status_code == 403:
                logger.error("  403 Forbidden - SearXNG is blocking the request.")
                logger.error("  Try these fixes:")
                logger.error("  1. Check if SearXNG is running: curl http://localhost:8080")
                logger.error("  2. Try a different URL: http://127.0.0.1:8080/search")
                logger.error("  3. Check SearXNG logs: docker logs <container_id>")
                logger.error("  4. Try using Firefox/Chrome User-Agent")
            return []
        
        data = response.json()
        
        # Parse SearXNG results
        results = []
        for result in data.get("results", []):
            url = result.get("url", "")
            if not url or "reddit.com" not in url.lower():
                continue
                
            results.append({
                "url": url,
                "title": result.get("title", ""),
                "description": result.get("content", result.get("snippet", "")),
                "engine": result.get("engine", ""),
                "source": "searxng",
                "score": 1.0,
            })
            
            if len(results) >= count:
                break
        
        logger.info(f"SearXNG found {len(results)} Reddit results for query: {query}")
        return results
        
    except requests.exceptions.ConnectionError:
        logger.error(f"Failed to connect to SearXNG at {searxng_url}")
        logger.error("Make sure SearXNG is running: docker run -d -p 8080:8080 searxng/searxng")
        return []
    except requests.exceptions.Timeout:
        logger.error(f"SearXNG request timed out after {timeout}s")
        return []
    except Exception as e:
        logger.error(f"SearXNG search error: {e}")
        return []



def search_reddit_with_queries(
    queries: List[str],
    searxng_url: str = SEARXNG_URL,
    max_results_per_query: int = 10,
    deduplicate: bool = True
) -> List[Dict[str, Any]]:
    """
    Search Reddit with multiple queries and deduplicate results.
    """
    all_results = []
    seen_urls = set()
    
    for i, query in enumerate(queries):
        logger.info(f"Searching with query {i+1}/{len(queries)}: {query}")
        
        results = search_reddit(
            query=query,
            searxng_url=searxng_url,
            count=max_results_per_query
        )
        
        if deduplicate:
            for result in results:
                url = result.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(result)
        else:
            all_results.extend(results)
        
        # Be respectful between queries
        if i < len(queries) - 1:
            time.sleep(2)  # Increased delay
    
    logger.info(f"Total unique Reddit results from {len(queries)} queries: {len(all_results)}")
    return all_results



def test_searxng_connection(searxng_url: str = SEARXNG_URL) -> bool:
    """
    Test if SearXNG is running and accessible.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    
    try:
        response = requests.get(
            searxng_url,
            params={"q": "test", "format": "json"},
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            logger.info(f"✅ SearXNG connection successful at {searxng_url}")
            return True
        else:
            logger.error(f"❌ SearXNG returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Failed to connect to SearXNG at {searxng_url}")
        logger.error("   Make sure SearXNG is running:")
        logger.error("   docker run -d -p 8080:8080 searxng/searxng")
        return False
    except Exception as e:
        logger.error(f"❌ SearXNG connection error: {e}")
        return False
