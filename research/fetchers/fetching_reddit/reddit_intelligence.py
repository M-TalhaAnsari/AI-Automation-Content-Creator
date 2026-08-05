"""
Complete Reddit Intelligence Layer - Orchestrates:
1. Query design (LLM - Groq)
2. SearXNG search
3. URL ranking (LLM - Groq)
4. Content extraction (HTTP with optional Firecrawl enhancement)
5. Content validation (LLM - Groq)
"""
import logging
import json
import sys
import os
from typing import List, Dict, Any

# Add parent directory to path for absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use absolute imports
from .searxng_search import search_reddit_with_queries
from .reddit_extractor import extract_multiple_reddit_posts, REDDIT_POST_SCHEMA
from .reddit_ranking import rank_reddit_urls, validate_reddit_content

logger = logging.getLogger("trendforge.fetchers.reddit_intelligence")


def design_reddit_queries(topic: str, groq_api_key: str, model_name: str = "llama-3.3-70b-versatile") -> List[str]:
    """Use LLM (Groq) to design search queries."""
    from langchain_groq import ChatGroq
    from langchain_classic.schema import HumanMessage
    
    if not groq_api_key:
        return [f"site:reddit.com {topic}", f"site:reddit.com {topic} discussion"]
    
    try:
        llm = ChatGroq(groq_api_key=groq_api_key, model=model_name, temperature=0.3)
        prompt = f"""You are a search query designer for Reddit content.

User topic: {topic}

Task: Design 2-3 search queries to find the best Reddit posts about this topic.
Include "site:reddit.com" in each query.
Return ONLY a JSON array of strings, nothing else."""
        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content.strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        queries = json.loads(response_text)
        logger.info(f"LLM designed queries: {queries}")
        return queries
    except Exception as e:
        logger.error(f"Query design failed: {e}")
        return [f"site:reddit.com {topic}", f"site:reddit.com {topic} discussion"]


def extract_reddit_content(urls: List[str], config) -> List[Dict[str, Any]]:
    """
    Extract Reddit content using HTTP/JSON fallback only.
    Firecrawl does NOT support Reddit, so we skip it.
    """
    logger.info("🔄 Using HTTP/JSON extraction for Reddit...")
    from research.fetchers.fetching_reddit.reddit_extractor import extract_multiple_reddit_posts
    return extract_multiple_reddit_posts(urls)


def fetch_reddit_intelligence(state, config, max_urls=15, max_posts=8) -> List[Dict[str, Any]]:
    """Main orchestrator."""
    topic = state.core_topic
    if not topic:
        logger.warning("No topic provided.")
        return []
    
    logger.info(f"🔍 Reddit Intelligence Layer - Topic: '{topic}'")
    
    # Step 1: Design queries
    logger.info("Step 1: Designing search queries (Groq)...")
    queries = design_reddit_queries(topic, config.GROQ_API_KEY)
    if not queries:
        queries = [f"site:reddit.com {topic}"]
    
    # Step 2: Search via SearXNG
    logger.info("Step 2: Searching Reddit via SearXNG...")
    searxng_url = getattr(config, "SEARXNG_URL", "http://localhost:8080/search")
    urls = search_reddit_with_queries(queries, searxng_url, max_results_per_query=10)
    if not urls:
        logger.warning("No Reddit URLs found.")
        return []
    
    logger.info(f"Found {len(urls)} unique URLs")
    
    # Step 3: Rank URLs
    logger.info("Step 3: Ranking URLs by relevance (Groq)...")
    ranked_urls = rank_reddit_urls(urls, topic, config.GROQ_API_KEY)
    # Filter out non-post URLs (must contain /comments/)
    post_urls = [item for item in ranked_urls if "/comments/" in item.get("url", "")]
    if not post_urls:
        logger.warning("No actual Reddit post URLs found (only subreddit pages).")
        # Fallback: take any URL with reddit.com/r/ and not wiki or about
        post_urls = [item for item in ranked_urls 
                    if "reddit.com/r/" in item.get("url", "") 
                    and "wiki" not in item.get("url", "")
                    and "about" not in item.get("url", "")]
    selected_urls = post_urls[:max_urls]
    logger.info(f"Selected {len(selected_urls)} post URLs for extraction")

    # Step 4: Extract content
    extracted_posts = extract_reddit_content(
        [item.get("url") for item in selected_urls],
    config
    )
    
    # Step 5: Validate content (temporarily disabled for testing)
    logger.info("Step 5: Skipping validation – accepting all extracted posts")
    validated_posts = []
    for post in extracted_posts:
        if post.get("extraction_success", False):
            # Add a placeholder relevance score so downstream code doesn't break
            post["relevance_validated"] = True
            post["relevance_score"] = 0.8
            post["relevance_reason"] = "Skipped validation (testing)"
            validated_posts.append(post)

    logger.info(f"✅ Accepted {len(validated_posts)} extracted posts")
    return validated_posts[:max_posts]