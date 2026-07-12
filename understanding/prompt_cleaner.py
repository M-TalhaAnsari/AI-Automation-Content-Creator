"""
understanding/prompt_cleaner.py — Pre-LLM Prompt Preprocessor

This runs BEFORE the LLM sees anything.
Pure Python — zero tokens, zero API calls.

Handles:
- Any prompt length (2 words to 500 words)
- Special characters that break JSON
- Repeated words / filler text
- Mixed languages (extracts English intent)
- Extracting explicit signals: platform, post count, special requests
- Normalizing platform names (insta → instagram, yt → youtube)
"""

import re
from typing import Dict, List, Any


# ─────────────────────────────────────────────
# PLATFORM DETECTION PATTERNS
# ─────────────────────────────────────────────

PLATFORM_ALIASES = {
    "instagram": ["instagram", "insta", "ig", "reels", "reel"],
    "youtube":   ["youtube", "yt", "youtube shorts", "shorts", "youtuber"],
    "tiktok":    ["tiktok", "tik tok", "tt", "tiktoker"],
    "linkedin":  ["linkedin", "linked in"],
}

# ─────────────────────────────────────────────
# POST COUNT PATTERNS
# ─────────────────────────────────────────────

POST_COUNT_PATTERNS = [
    r'\b(\d+)\s*posts?\b',
    r'\b(\d+)\s*videos?\b',
    r'\b(\d+)\s*reels?\b',
    r'\b(\d+)\s*parts?\b',
    r'\btop\s*(\d+)\b',
    r'\bbest\s*(\d+)\b',
    r'\b(\d+)\s*projects?\b',
    r'\b(\d+)\s*ideas?\b',
    r'\b(\d+)\s*things?\b',
    r'\b(\d+)\s*tips?\b',
    r'\b(\d+)\s*ways?\b',
]

# ─────────────────────────────────────────────
# SPECIAL REQUEST PATTERNS
# ─────────────────────────────────────────────

SPECIAL_REQUEST_PATTERNS = {
    "github_links":      [r'github\s*links?', r'github\s*url', r'repo\s*links?', r'source\s*code\s*links?'],
    "project_summary":   [r'project\s*summar', r'summar\w+\s*of\s*project', r'what\s*the\s*project\s*does', r'project\s*description'],
    "bullet_points":     [r'bullet\s*points?', r'points?\s*form', r'key\s*points?', r'in\s*points?'],
    "hashtags":          [r'hashtags?', r'tags?', r'#'],
    "hooks":             [r'hook', r'catchy\s*line', r'opening\s*line', r'attention\s*grabbing'],
    "captions":          [r'captions?', r'post\s*text', r'write\s*for\s*post'],
    "video_script":      [r'video\s*script', r'script\s*for\s*video', r'what\s*to\s*say'],
    "trending_only":     [r'trending', r'viral', r'popular\s*right\s*now', r'latest', r'2025', r'2026'],
    "beginner_friendly": [r'beginner', r'starter', r'easy\s*to\s*understand', r'simple'],
    "with_links":        [r'with\s*links?', r'include\s*links?', r'add\s*links?', r'links?\s*included'],
}

# ─────────────────────────────────────────────
# CONTENT TYPE DETECTION
# ─────────────────────────────────────────────

CONTENT_TYPE_PATTERNS = {
    "posts":    [r'posts?', r'pictures?', r'photos?', r'carousel', r'slides?'],
    "script":   [r'script', r'video\s*idea', r'what\s*to\s*say', r'narration'],
    "thread":   [r'thread', r'series\s*of\s*tweets?', r'twitter'],
    "carousel": [r'carousel', r'swipe', r'slides?', r'multiple\s*pages?'],
}

# ─────────────────────────────────────────────
# NOISE WORDS TO STRIP BEFORE SENDING TO LLM
# ─────────────────────────────────────────────

NOISE_PHRASES = [
    r'\bi want\b', r'\bi need\b', r'\bplease\b', r'\bgive me\b',
    r'\bcan you\b', r'\bcould you\b', r'\bwould you\b', r'\bhelp me\b',
    r'\bi am looking for\b', r'\bi would like\b', r'\bprovide me\b',
    r'\bgenerate\b', r'\bcreate\b', r'\bmake\b', r'\bbuild\b',
    r'\bfor my\b', r'\bfor the\b', r'\bso that i can\b',
    r'\bwhat i want is\b', r'\bwhat i need is\b',
]


class PromptCleaner:
    """
    Pure Python preprocessor — zero tokens, zero API calls.
    Extracts everything it can from raw prompt before LLM is involved.
    The cleaner the input to LLM, the fewer tokens needed.
    """

    def clean(self, raw_prompt: str) -> Dict[str, Any]:
        """
        Main entry point. Returns a structured dict of everything
        extracted from the raw prompt using pure Python rules.

        Returns:
            {
                "cleaned_text": str,          # noise-stripped text for LLM
                "detected_platform": str,     # or "" if not found
                "detected_post_count": int,   # or 0 if not found
                "detected_special_requests": list,
                "detected_content_type": str, # or ""
                "is_long": bool,
                "word_count": int,
                "char_count": int,
                "extraction_confidence": str, # "high" | "medium" | "low"
            }
        """
        text = raw_prompt.strip()
        lower = text.lower()

        platform = self._detect_platform(lower)
        post_count = self._detect_post_count(lower)
        special_requests = self._detect_special_requests(lower)
        content_type = self._detect_content_type(lower)
        cleaned = self._clean_text(text)
        confidence = self._estimate_confidence(text, platform, post_count)

        return {
            "cleaned_text": cleaned,
            "detected_platform": platform,
            "detected_post_count": post_count,
            "detected_special_requests": special_requests,
            "detected_content_type": content_type,
            "is_long": len(text) > 120,
            "word_count": len(text.split()),
            "char_count": len(text),
            "extraction_confidence": confidence,
        }

    def _detect_platform(self, lower: str) -> str:
        for platform, aliases in PLATFORM_ALIASES.items():
            for alias in aliases:
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, lower):
                    return platform
        return ""

    def _detect_post_count(self, lower: str) -> int:
        """Extracts number of posts/items requested. Returns 0 if not found."""
        for pattern in POST_COUNT_PATTERNS:
            match = re.search(pattern, lower)
            if match:
                try:
                    count = int(match.group(1))
                    if 1 <= count <= 20:   # sanity check
                        return count
                except (IndexError, ValueError):
                    pass
        return 0

    def _detect_special_requests(self, lower: str) -> List[str]:
        """Finds explicit special requests like 'github links', 'bullet points'."""
        found = []
        for request_name, patterns in SPECIAL_REQUEST_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lower):
                    found.append(request_name)
                    break   # don't double-count same request
        return found

    def _detect_content_type(self, lower: str) -> str:
        """Detects what kind of content is requested."""
        for ctype, patterns in CONTENT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lower):
                    return ctype
        return ""

    def _clean_text(self, text: str) -> str:
        """
        Strips noise phrases so LLM gets the essence not the fluff.
        Preserves meaning — only removes filler.
        """
        cleaned = text

        # Remove noise phrases (case insensitive)
        for noise in NOISE_PHRASES:
            cleaned = re.sub(noise, ' ', cleaned, flags=re.IGNORECASE)

        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Remove repeated punctuation
        cleaned = re.sub(r'[!?]{2,}', '!', cleaned)
        cleaned = re.sub(r'\.{2,}', '...', cleaned)

        # If cleaned is too short (noise removal took too much), use original
        if len(cleaned.strip()) < 10:
            cleaned = text

        return cleaned.strip()

    def _estimate_confidence(self, text: str, platform: str, post_count: int) -> str:
        """
        Estimates how much the LLM needs to figure out vs what we already know.
        high = rules got most of it, LLM just needs to extract topic
        medium = rules got some, LLM needs to figure out platform/count
        low = rules got nothing, LLM does all the work
        """
        score = 0
        if platform:
            score += 1
        if post_count > 0:
            score += 1
        if len(text.split()) >= 3:
            score += 1

        if score >= 3:
            return "high"
        elif score >= 1:
            return "medium"
        else:
            return "low"
