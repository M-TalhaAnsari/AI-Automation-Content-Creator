#!/usr/bin/env python3
"""
Test RSS-based Reddit fetcher with a simple topic.
No API keys required – works immediately.
"""
import sys
import os
import json
import re
import time
import logging
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("reddit_rss_test")

# Try to import feedparser
try:
    import feedparser
except ImportError:
    print("❌ feedparser not installed. Installing...")
    os.system("pip install feedparser")
    import feedparser

# ------------------------------------------------------------
# Subreddit Mapping (same as what would be in config)
# ------------------------------------------------------------
SUBREDDIT_MAP = {
    "tech": ["technology", "MachineLearning", "artificial", "programming", "Python"],
    "business": ["Entrepreneur", "startups", "business", "personalfinance"],
    "lifestyle": ["fitness", "travel", "food", "minimalism"],
    "entertainment": ["movies", "gaming", "music", "television"],
    "unknown": ["AskReddit", "news", "worldnews", "interesting"],
}

PLATFORM_SUBREDDIT = {
    "instagram": ["Instagram", "socialmedia"],
    "youtube": ["youtube", "video"],
    "tiktok": ["TikTok"],
    "linkedin": ["LinkedIn", "careerguidance"],
}

# ------------------------------------------------------------
# The RSS Fetcher
# ------------------------------------------------------------
def fetch_reddit_rss(topic: str, category: str = "unknown", platform: str = None) -> List[Dict[str, Any]]:
    """
    Fetch Reddit posts via RSS for a given topic.
    """
    if not topic:
        logger.warning("No topic provided. Fetching top posts instead.")
        topic = None
    
    # Get subreddits for this category
    subreddits = SUBREDDIT_MAP.get(category, SUBREDDIT_MAP["unknown"]).copy()
    
    # Add platform-specific subreddits if applicable
    if platform and platform in PLATFORM_SUBREDDIT:
        subreddits = PLATFORM_SUBREDDIT[platform] + subreddits
    
    # If topic is specific, try to add relevant subreddits
    if topic:
        topic_words = topic.lower().split()
        for word in topic_words:
            if word in ["python", "javascript", "rust", "golang", "react", "vue", "docker", "kubernetes"]:
                subreddits.append(word.capitalize())
            elif word in ["ai", "ml", "llm", "gpt", "openai", "claude", "gemini"]:
                subreddits.extend(["artificial", "MachineLearning", "OpenAI", "ChatGPT"])
            elif word in ["fitness", "gym", "workout", "running", "yoga"]:
                subreddits.append("Fitness")
    
    # Deduplicate and limit
    subreddits = list(dict.fromkeys(subreddits))[:5]
    
    logger.info(f"Searching subreddits: {subreddits}")
    
    all_items = []
    
    for subreddit in subreddits:
        try:
            # Build RSS URL
            if topic:
                # Search for the topic within the subreddit
                query = topic.replace(' ', '+')
                url = f"https://www.reddit.com/r/{subreddit}/search.rss?q={query}&sort=relevance&limit=10"
            else:
                # If no topic, get top posts from today
                url = f"https://www.reddit.com/r/{subreddit}/top.rss?t=day&limit=10"
            
            logger.info(f"  Fetching: {url}")
            
            # Parse RSS feed
            feed = feedparser.parse(url)
            
            # Check for errors
            if feed.bozo:
                logger.warning(f"  RSS parsing warning for {subreddit}: {feed.bozo_exception}")
                if feed.status == 404:
                    logger.warning(f"  Subreddit r/{subreddit} not found")
                continue
            
            # Check if we got any entries
            if not feed.entries:
                logger.info(f"  No entries found for r/{subreddit}")
                continue
            
            # Extract entries
            count = 0
            for entry in feed.entries[:10]:
                # Clean up the summary (remove HTML)
                summary = entry.get("summary", "")
                if summary:
                    # Remove HTML tags
                    summary = re.sub(r'<[^>]+>', '', summary)
                    # Remove extra whitespace
                    summary = re.sub(r'\s+', ' ', summary).strip()
                    # Limit length
                    if len(summary) > 300:
                        summary = summary[:300] + "..."
                
                # Get the link
                link = entry.get("link", "")
                if not link:
                    # Try to get from the entry's id
                    link = entry.get("id", "")
                
                # Extract author
                author = entry.get("author", "Unknown")
                if hasattr(entry, 'author_detail') and entry.author_detail:
                    author = entry.author_detail.get("name", author)
                
                all_items.append({
                    "title": entry.get("title", "No title").strip(),
                    "link": link,
                    "summary": summary or "Reddit post from RSS feed.",
                    "source": "reddit",
                    "subreddit": subreddit,
                    "author": author,
                    "published": entry.get("published", ""),
                })
                count += 1
            
            logger.info(f"  Retrieved {count} items from r/{subreddit}")
            
            # Be respectful – small delay between subreddits
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error fetching Reddit RSS for r/{subreddit}: {e}")
            continue
    
    logger.info(f"✅ Total: {len(all_items)} items retrieved")
    return all_items

# ------------------------------------------------------------
# Test Function
# ------------------------------------------------------------
def test_rss_fetcher():
    """Test the RSS fetcher with different topics."""
    
    print("=" * 70)
    print("  REDDIT RSS FETCHER - TEST")
    print("=" * 70)
    
    # Test topics
    test_cases = [
        {"topic": "artificial intelligence", "category": "tech"},
        {"topic": "Python programming", "category": "tech"},
        {"topic": "startup funding", "category": "business"},
        {"topic": "fitness motivation", "category": "lifestyle"},
        {"topic": "new movies", "category": "entertainment"},
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'-'*70}")
        print(f"TEST {i}: Topic='{test['topic']}' Category='{test['category']}'")
        print("-" * 70)
        
        items = fetch_reddit_rss(
            topic=test['topic'],
            category=test['category']
        )
        
        if not items:
            print("❌ No items found.")
            continue
        
        print(f"✅ Found {len(items)} items\n")
        
        # Show first 3 items
        for j, item in enumerate(items[:3], 1):
            print(f"--- Post {j} ---")
            print(f"Title:    {item.get('title', 'N/A')}")
            print(f"Subreddit: r/{item.get('subreddit', 'N/A')}")
            print(f"Author:   {item.get('author', 'N/A')}")
            print(f"Summary:  {item.get('summary', 'N/A')[:100]}...")
            print(f"Link:     {item.get('link', 'N/A')}")
            print()
        
        if len(items) > 3:
            print(f"... and {len(items)-3} more items.")
    
    # Test with platform-specific subreddits
    print(f"\n{'-'*70}")
    print(f"TEST: Platform-specific (Instagram)")
    print("-" * 70)
    
    items = fetch_reddit_rss(
        topic="social media growth",
        category="business",
        platform="instagram"
    )
    
    if items:
        print(f"✅ Found {len(items)} items from Instagram-related subreddits")
        for i, item in enumerate(items[:3], 1):
            print(f"  {i}. {item.get('title', 'N/A')[:60]}... (r/{item.get('subreddit', 'N/A')})")
    else:
        print("❌ No items found")
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_rss_fetcher()