"""
config.py — TrendForge Central Configuration

Single source of truth for all API keys, model settings, and source toggles.
Every other file reads from CONFIG — nothing should redefine these values elsewhere.
"""

import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────
# MODEL CONFIGURATION
# ─────────────────────────────────────────────

@dataclass
class ModelConfig:
    # Groq — used for fast/cheap classification, routing, intent extraction
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model_small: str = os.getenv("GROQ_MODEL_SMALL", "openai/gpt-oss-20b")
    groq_model_large: str = os.getenv("GROQ_MODEL_LARGE", "openai/gpt-oss-120b")

    # Gemini — used for final creative content generation
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    # Temperature: low = consistent/deterministic, high = creative
    routing_temperature: float = 0.0
    generation_temperature: float = 0.85


# ─────────────────────────────────────────────
# DATA SOURCE CONFIGURATION
# ─────────────────────────────────────────────

@dataclass
class SourceConfig:
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")

    reddit_client_id: str = os.getenv("REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    reddit_user_agent: str = os.getenv("REDDIT_USER_AGENT", "TrendForge/1.0")

    # GitHub works without a token (60 req/hour); token raises limit to 5000/hour
    github_token: str = os.getenv("GITHUB_TOKEN", "")

    # Per-source on/off switches
    enable_github: bool = os.getenv("ENABLE_GITHUB", "true").lower() == "true"
    enable_reddit: bool = os.getenv("ENABLE_REDDIT", "true").lower() == "true"
    enable_youtube: bool = os.getenv("ENABLE_YOUTUBE", "true").lower() == "true"
    enable_google_trends: bool = os.getenv("ENABLE_GOOGLE_TRENDS", "true").lower() == "true"
    enable_hackernews: bool = os.getenv("ENABLE_HACKERNEWS", "true").lower() == "true"
    enable_paperswithcode: bool = os.getenv("ENABLE_PAPERSWITHCODE", "true").lower() == "true"
    enable_huggingface: bool = os.getenv("ENABLE_HUGGINGFACE", "true").lower() == "true"
    enable_tavily: bool = os.getenv("ENABLE_TAVILY", "true").lower() == "true"


# ─────────────────────────────────────────────
# SOURCE ROUTING — which sources serve which content category
#
# NOTE: category itself is decided by the LLM in intent_extractor.py,
# NOT by keyword matching here. This map only answers: given a category
# the LLM already decided, which sources should we fetch from?
# ─────────────────────────────────────────────

SOURCE_MAP = {
    "tech":          ["github", "reddit"],
    "business":      ["reddit", "google_trends", "tavily"],
    "lifestyle":     ["reddit", "youtube", "google_trends", "tavily"],
    "entertainment": ["reddit", "youtube", "google_trends", "tavily"],
    "education":     ["reddit", "youtube", "google_trends"],
    "news":          ["tavily", "google_trends"],
    "unknown":       ["google_trends", "reddit", "tavily"],
}


# ─────────────────────────────────────────────
# PLATFORM SETTINGS — tone/format rules per output platform
# ─────────────────────────────────────────────

PLATFORM_SETTINGS = {
    "instagram": {
        "post_format": "image_caption",
        "max_caption_chars": 2200,
        "hashtag_count": 15,
        "tone": "aspirational, visual, lifestyle-driven",
        "hook_style": "bold statement or curiosity gap",
        "emoji_usage": "high",
    },
    "youtube": {
        "post_format": "video_script",
        "max_caption_chars": 5000,
        "hashtag_count": 10,
        "tone": "informative, engaging, educational",
        "hook_style": "question or surprising fact",
        "emoji_usage": "medium",
    },
    "linkedin": {
        "post_format": "professional_post",
        "max_caption_chars": 3000,
        "hashtag_count": 5,
        "tone": "professional, insightful, thought leadership",
        "hook_style": "bold insight or personal story",
        "emoji_usage": "low",
    },
    "tiktok": {
        "post_format": "short_video_script",
        "max_caption_chars": 2200,
        "hashtag_count": 10,
        "tone": "raw, authentic, Gen-Z, fast paced",
        "hook_style": "pattern interrupt, POV",
        "emoji_usage": "high",
    },
}

SUPPORTED_PLATFORMS = list(PLATFORM_SETTINGS.keys())


# ─────────────────────────────────────────────
# SYSTEM SETTINGS
#
# NOTE: not all fields below are confirmed to be read elsewhere yet —
# verify usage as each remaining file is cleaned, remove if truly unused.
# ─────────────────────────────────────────────

@dataclass
class SystemConfig:
    default_post_count: int = 5
    default_platform: str = "instagram"
    max_prompt_length: int = 2000
    max_fetch_results_per_source: int = 8
    memory_enabled: bool = True
    memory_path: str = "memory/sessions.json"
    output_dir: str = "output"
    show_token_report: bool = True
    show_agent_logs: bool = False


# ─────────────────────────────────────────────
# GLOBAL CONFIG — single instance, imported everywhere as CONFIG
# ─────────────────────────────────────────────

class TrendForgeConfig:
    def __init__(self):
        self.models = ModelConfig()
        self.sources = SourceConfig()
        self.system = SystemConfig()

    # ── Read-only UPPERCASE adapters ─────────────────────────────
    # WHY THESE EXIST: fetchers receive CONFIG directly (not CONFIG.sources)
    # and expect flat UPPERCASE attribute names. These properties are the
    # ONLY place that mapping happens — the dataclasses above remain the
    # single source of truth. Never assign to these properties directly.
    @property
    def GROQ_API_KEY(self):
        return self.models.groq_api_key

    @property
    def GEMINI_API_KEY(self):
        return self.models.gemini_api_key

    @property
    def YOUTUBE_API_KEY(self):
        return self.sources.youtube_api_key

    @property
    def TAVILY_API_KEY(self):
        return self.sources.tavily_api_key

    @property
    def GITHUB_TOKEN(self):
        return self.sources.github_token

    @property
    def REDDIT_USER_AGENT(self):
        return self.sources.reddit_user_agent

    def validate(self) -> List[str]:
        """
        Returns human-readable warnings for missing config.
        Never raises — the system should degrade gracefully, not crash.
        """
        warnings = []

        if not self.models.groq_api_key:
            warnings.append("GROQ_API_KEY missing — routing + parsing will fail.")
        if not self.models.gemini_api_key:
            warnings.append("GEMINI_API_KEY missing — content generation will fail.")
        if not self.sources.tavily_api_key:
            warnings.append("TAVILY_API_KEY missing — web search fallback disabled.")
        if not self.sources.youtube_api_key:
            warnings.append("YOUTUBE_API_KEY missing — YouTube source disabled.")
        if not self.sources.reddit_client_id:
            warnings.append("REDDIT credentials missing — Reddit source disabled.")
        if not self.sources.github_token:
            warnings.append("GITHUB_TOKEN missing — GitHub limited to 60 req/hour (still works).")

        return warnings

    def available_sources(self) -> List[str]:
        """Returns sources that are actually usable right now (enabled + credentials present)."""
        available = []
        s = self.sources

        if s.enable_github:
            available.append("github")
        if s.enable_hackernews:
            available.append("hackernews")
        if s.enable_paperswithcode:
            available.append("paperswithcode")
        if s.enable_huggingface:
            available.append("huggingface")
        if s.enable_google_trends:
            available.append("google_trends")
        if s.enable_reddit and s.reddit_client_id:
            available.append("reddit")
        if s.enable_youtube and s.youtube_api_key:
            available.append("youtube")
        if s.enable_tavily and s.tavily_api_key:
            available.append("tavily")

        return available


# Singleton — import this everywhere, never instantiate TrendForgeConfig() again
CONFIG = TrendForgeConfig()