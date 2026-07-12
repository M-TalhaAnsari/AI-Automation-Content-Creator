"""
Reddit content extraction from HTML to structured JSON.
Handles HTML parsing, content extraction, and error handling.
"""
import re
import json
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from fetchers.base import safe_request

logger = logging.getLogger("trendforge.fetchers.reddit_extractor")

# Structured JSON schema for Reddit posts
REDDIT_POST_SCHEMA = {
    "url": "",
    "title": "",
    "subreddit": "",
    "author": "",
    "score": 0,
    "comments_count": 0,
    "post_content": "",
    "top_comments": [],
    "extraction_success": False,
    "extraction_error": None,
}

def fetch_reddit_post(url: str, timeout: int = 15) -> Optional[str]:
    """
    Fetch Reddit content - tries JSON first, falls back to old.reddit.com HTML.
    """
    # Try JSON endpoint first
    json_url = url + ".json"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(json_url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return response.text, "json"
    except:
        pass
    
    # Fallback: Use old.reddit.com (stable HTML structure)
    old_url = url.replace("www.reddit.com", "old.reddit.com")
    logger.info(f"Falling back to old.reddit.com: {old_url}")
    
    try:
        response = requests.get(old_url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return response.text, "html"
    except Exception as e:
        logger.error(f"Failed to fetch old.reddit.com: {e}")
    
    return None, None


def extract_from_json(json_data: str) -> Dict[str, Any]:
    """
    Extract structured data from Reddit's JSON endpoint.
    This is the preferred method as it's already structured.
    """
    try:
        data = json.loads(json_data)
        
        # Reddit JSON endpoint returns a list
        # First element contains post data, second contains comments
        if not data or not isinstance(data, list) or len(data) < 2:
            return {**REDDIT_POST_SCHEMA, "extraction_success": False, "extraction_error": "Invalid JSON structure"}
        
        post_data = data[0].get("data", {})
        comments_data = data[1].get("data", {})
        
        post = post_data.get("children", [{}])[0].get("data", {})
        
        # Extract top comments
        top_comments = []
        for comment in comments_data.get("children", [])[:5]:
            comment_data = comment.get("data", {})
            if not comment_data.get("body", ""):
                continue
            top_comments.append({
                "author": comment_data.get("author", ""),
                "body": comment_data.get("body", ""),
                "score": comment_data.get("score", 0),
            })
        
        return {
            "url": post.get("url", ""),
            "title": post.get("title", ""),
            "subreddit": post.get("subreddit", ""),
            "author": post.get("author", ""),
            "score": post.get("score", 0),
            "comments_count": post.get("num_comments", 0),
            "post_content": post.get("selftext", "") or post.get("title", ""),
            "top_comments": top_comments,
            "extraction_success": True,
            "extraction_error": None,
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {**REDDIT_POST_SCHEMA, "extraction_success": False, "extraction_error": f"JSON decode: {str(e)}"}
    except Exception as e:
        logger.error(f"JSON extraction error: {e}")
        return {**REDDIT_POST_SCHEMA, "extraction_success": False, "extraction_error": str(e)}


def extract_from_html(html: str, url: str) -> Dict[str, Any]:
    """
    Improved HTML extraction for Reddit posts.
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get title (usually in h1 with specific class)
        title_elem = soup.find('h1', {'class': re.compile(r'title|post-title|_1qeIAgB0cPwnLhDF9XSiJM')})
        title = title_elem.text.strip() if title_elem else ""
        
        # Get subreddit from URL if not in meta
        subreddit = ""
        subreddit_match = re.search(r'/r/([^/]+)/', url)
        if subreddit_match:
            subreddit = subreddit_match.group(1)
        else:
            subreddit_elem = soup.find('a', {'href': re.compile(r'/r/[^/]+/$')})
            if subreddit_elem:
                subreddit = subreddit_elem.text.strip()
        
        # Get author
        author = ""
        author_elem = soup.find('a', {'class': re.compile(r'author|_2tbHP6ZydRpjI44J3syuqC')})
        if author_elem:
            author = author_elem.text.strip()
        else:
            author_match = re.search(r'/u/([^/]+)', html)
            if author_match:
                author = author_match.group(1)
        
        # Get post content (the actual text) – look for the main content div
        content = ""
        content_elems = soup.find_all('div', {'class': re.compile(r'usertext-body|_1qeIAgB0cPwnLhDF9XSiJM|md')})
        if content_elems:
            # Take the first one that has text
            for elem in content_elems:
                text = elem.text.strip()
                if len(text) > 50:  # likely actual content
                    content = text
                    break
            if not content:
                content = content_elems[0].text.strip() if content_elems else ""
        
        # If no content found, try to get the post description from meta
        if not content:
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc:
                content = meta_desc.get('content', '')
        
        # Get score
        score = 0
        score_elem = soup.find('span', {'class': re.compile(r'score|_1rZY4_3h8Z7XK0pNfYz7v')})
        if score_elem:
            score_text = score_elem.text.strip()
            score = int(re.sub(r'[^0-9]', '', score_text)) if re.search(r'\d', score_text) else 0
        
        # Get comments count
        comments = 0
        comments_elem = soup.find('span', {'class': re.compile(r'comments|_3WgW9tFwC_3qZ1k9W4fX1')})
        if comments_elem:
            comments_text = comments_elem.text.strip()
            comments = int(re.search(r'(\d+)', comments_text).group(1)) if re.search(r'\d+', comments_text) else 0
        
        # Get top comments (simple extraction from comment divs)
        top_comments = []
        comment_divs = soup.find_all('div', {'class': re.compile(r'comment|_1qeIAgB0cPwnLhDF9XSiJM')})[:5]
        for div in comment_divs:
            author_elem = div.find('a', {'class': re.compile(r'author|_2tbHP6ZydRpjI44J3syuqC')})
            body_elem = div.find('div', {'class': re.compile(r'usertext-body|md|_1qeIAgB0cPwnLhDF9XSiJM')})
            if body_elem:
                top_comments.append({
                    "author": author_elem.text.strip() if author_elem else "",
                    "body": body_elem.text.strip(),
                    "score": 0,
                })
        
        return {
            "url": url,
            "title": title,
            "subreddit": subreddit,
            "author": author,
            "score": score,
            "comments_count": comments,
            "post_content": content,
            "top_comments": top_comments,
            "extraction_success": True,
            "extraction_error": None,
        }
        
    except Exception as e:
        logger.error(f"HTML extraction error: {e}")
        return {**REDDIT_POST_SCHEMA, "url": url, "extraction_success": False, "extraction_error": str(e)}
    

def extract_reddit_content(url: str) -> Dict[str, Any]:
    """
    Main extraction function - tries JSON first, then falls back to HTML.
    """
    # Fetch the content
    content, content_type = fetch_reddit_post(url)
    
    if not content:
        return {
            **REDDIT_POST_SCHEMA,
            "url": url,
            "extraction_success": False,
            "extraction_error": "Failed to fetch content"
        }
    
    # Extract based on content type
    if content_type == "json":
        result = extract_from_json(content)
    else:
        result = extract_from_html(content, url)
    
    # Ensure URL is set
    result["url"] = url
    
    return result

def extract_reddit_content_fallback(url: str) -> Dict[str, Any]:
    """
    Extract Reddit content using old.reddit.com HTML (stable structure).
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        # Use old.reddit.com directly
        old_url = url.replace("www.reddit.com", "old.reddit.com")
        response = requests.get(old_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return {
                **REDDIT_POST_SCHEMA,
                "url": url,
                "extraction_success": False,
                "extraction_error": f"HTTP {response.status_code}"
            }
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title - old.reddit.com uses <a class="title">
        title_elem = soup.find('a', {'class': 'title'})
        title = title_elem.text.strip() if title_elem else ""
        
        # Extract subreddit from URL
        subreddit = ""
        subreddit_match = re.search(r'/r/([^/]+)/', url)
        if subreddit_match:
            subreddit = subreddit_match.group(1)
        
        # Extract author - old.reddit.com uses <a class="author">
        author = ""
        author_elem = soup.find('a', {'class': 'author'})
        if author_elem:
            author = author_elem.text.strip()
        
        # Extract post content - target the post's usertext-body
        content = ""
        # Find the main post container (usually a div with class "usertext" or "thing")
        post_thing = soup.find('div', {'class': 'thing'})
        if post_thing:
            # Look for usertext-body within this container
            body_div = post_thing.find('div', {'class': 'usertext-body'})
            if body_div:
                paragraphs = body_div.find_all('p')
                content = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])

        # If not found, fallback to the first usertext-body not inside a comment
        if not content:
            for body_div in soup.find_all('div', {'class': 'usertext-body'}):
                # Check if it's inside a comment (has parent with class 'comment')
                if body_div.find_parent('div', {'class': 'comment'}) is None:
                    paragraphs = body_div.find_all('p')
                    content = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
                    if content:
                        break
            
        # Extract score - old.reddit.com uses <span class="score"]
        score = 0
        score_elem = soup.find('span', {'class': 'score'})
        if score_elem:
            score_text = score_elem.text.strip()
            score = int(re.sub(r'[^0-9-]', '', score_text)) if score_text else 0
        
        # Extract comments count
        comments = 0
        comments_elem = soup.find('a', {'class': 'bylink'}, text=re.compile(r'comments'))
        if comments_elem:
            comments_text = comments_elem.text.strip()
            match = re.search(r'(\d+)', comments_text)
            if match:
                comments = int(match.group(1))
        
        # Extract top comments (limited to 5)
        top_comments = []
        comment_divs = soup.find_all('div', {'class': 'comment'})[:5]
        for div in comment_divs:
            author_elem = div.find('a', {'class': 'author'})
            body_elem = div.find('div', {'class': 'usertext-body'})
            if body_elem:
                # Extract comment text
                comment_text = body_elem.text.strip()
                # Remove "permalink embed save parent" etc.
                comment_text = re.sub(r'permalink\s+embed\s+save\s+parent.*$', '', comment_text, flags=re.IGNORECASE)
                if comment_text:
                    top_comments.append({
                        "author": author_elem.text.strip() if author_elem else "",
                        "body": comment_text[:500],  # Limit length
                        "score": 0,
                    })
        
        return {
            "url": url,
            "title": title,
            "subreddit": subreddit,
            "author": author,
            "score": score,
            "comments_count": comments,
            "post_content": content,
            "top_comments": top_comments,
            "extraction_success": True,
            "extraction_error": None,
        }
        
    except Exception as e:
        logger.error(f"Fallback extraction error for {url}: {e}")
        return {
            **REDDIT_POST_SCHEMA,
            "url": url,
            "extraction_success": False,
            "extraction_error": str(e)
        }
    

def extract_multiple_reddit_posts(urls: List[str]) -> List[Dict[str, Any]]:
    """Extract content from multiple Reddit URLs."""
    results = []
    for url in urls:
        try:
            extracted = extract_reddit_content_fallback(url)
            results.append(extracted)
            logger.info(f"Extracted: {'✅' if extracted.get('extraction_success') else '❌'} {url[:60]}...")
        except Exception as e:
            logger.error(f"Failed to extract {url}: {e}")
            results.append({
                **REDDIT_POST_SCHEMA,
                "url": url,
                "extraction_success": False,
                "extraction_error": str(e)
            })
    return results