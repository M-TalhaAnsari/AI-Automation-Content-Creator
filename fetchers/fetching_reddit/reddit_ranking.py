"""
LLM-powered URL ranking and content validation for Reddit.
Uses LLaMA3 8B via Groq for intelligent ranking and validation.
"""
import json
import logging
from typing import List, Dict, Any, Tuple
from langchain_groq import ChatGroq
from langchain_classic.schema import HumanMessage

logger = logging.getLogger("trendforge.fetchers.reddit_ranking")

def rank_reddit_urls(
    urls: List[Dict[str, Any]],
    query: str,
    groq_api_key: str,
    model_name: str = "llama-3.3-70b-versatile"
) -> List[Dict[str, Any]]:
    """
    Use LLM to rank Reddit URLs by relevance to the user's query.
    
    Args:
        urls: List of URL metadata from Brave
        query: User's original query
        groq_api_key: Groq API key
        model_name: LLM model name
    
    Returns:
        Ranked list of URLs with relevance scores
    """
    if not groq_api_key or not urls:
        return urls
    
    try:
        llm = ChatGroq(
            groq_api_key=groq_api_key,
            model_name=model_name,
            temperature=0.3
        )
        
        # Prepare URL list for LLM
        url_list = "\n".join([
            f"{i+1}. {item.get('title', '')} - {item.get('description', '')}\n   URL: {item.get('url', '')}"
            for i, item in enumerate(urls)
        ])
        
        prompt = f"""You are an intelligent Reddit content ranker.
        
User query: {query}

Here are Reddit URLs found from search:
{url_list}

Task: Rank these URLs by relevance to the user's query. Consider:
1. Does the title/content match the query?
2. Is it likely to contain valuable information?
3. Is it a question/answer or discussion post?
4. Is the subreddit relevant?

Return a JSON array with the URLs reordered from most relevant to least relevant.
Each item should have: {{"url": "url", "relevance_score": 0.0-1.0, "reason": "brief reason"}}

Only return the JSON array, nothing else."""

        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content.strip()
        
        # Parse JSON response
        # Handle potential markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        ranked = json.loads(response_text)
        
        # Create a mapping of URL to rank data
        url_rank_map = {item["url"]: item for item in ranked}
        
        # Add ranking to original items
        for item in urls:
            url = item.get("url", "")
            rank_data = url_rank_map.get(url, {})
            item["relevance_score"] = rank_data.get("relevance_score", 0.5)
            item["relevance_reason"] = rank_data.get("reason", "No reason provided")
            item["rank"] = len(urls) - urls.index(item) if url in url_rank_map else len(urls)
        
        # Sort by relevance score
        sorted_urls = sorted(urls, key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        logger.info(f"Ranked {len(sorted_urls)} URLs for query: {query}")
        return sorted_urls
        
    except Exception as e:
        logger.error(f"URL ranking failed: {e}")
        return urls


def validate_reddit_content(
    extracted_content: Dict[str, Any],
    query: str,
    groq_api_key: str,
    model_name: str = "llama-3.3-70b-versatile"
) -> Tuple[bool, float, str]:
    """
    Validate that extracted Reddit content matches the user's query.
    
    Args:
        extracted_content: Extracted Reddit post data
        query: User's original query
        groq_api_key: Groq API key
        model_name: LLM model name
    
    Returns:
        (is_valid, relevance_score, reason)
    """
    if not groq_api_key:
        # If no API key, do basic keyword matching
        title = extracted_content.get("title", "").lower()
        content = extracted_content.get("post_content", "").lower()
        query_words = query.lower().split()
        
        matches = sum(1 for word in query_words if word in title or word in content)
        score = matches / max(len(query_words), 1) if query_words else 0.5
        
        return score > 0.3, min(score, 1.0), "Basic keyword matching"
    
    try:
        llm = ChatGroq(
            groq_api_key=groq_api_key,
            model_name=model_name,
            temperature=0.2
        )
        
        prompt = f"""You are a content relevance validator for AI content generation.

User query: {query}

Extracted Reddit post:
Title: {extracted_content.get('title', '')}
Subreddit: {extracted_content.get('subreddit', '')}
Author: {extracted_content.get('author', '')}
Score: {extracted_content.get('score', 0)}
Content: {extracted_content.get('post_content', '')[:500]}

Task: Validate if this Reddit post is actually relevant to the user's query.
Consider:
1. Does the content directly relate to the query topic?
2. Would this be useful for generating content about the query?
3. Is it off-topic or too generic?

Return a JSON object:
{{
    "is_valid": true/false,
    "relevance_score": 0.0-1.0,
    "reason": "brief explanation"
}}

Only return the JSON object, nothing else."""

        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content.strip()
        
        # Parse JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        result = json.loads(response_text)
        return (
            result.get("is_valid", True),
            result.get("relevance_score", 0.5),
            result.get("reason", "No reason provided")
        )
        
    except Exception as e:
        logger.error(f"Content validation failed: {e}")
        return True, 0.5, f"Validation error: {e}"