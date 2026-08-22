"""
config.py — TrendForge Central Configuration
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ImagingConfig:
    """
    Configuration for the image generation subsystem.

    All values are read from environment variables so you can switch providers,
    models, or storage backends without touching code.

    Provider selection:
      IMAGE_PROVIDER — Active provider name. Options:
                        "mock"          → Synthetic PNG (dev/test, no external calls)
                        "pollinations"  → FREE, Flux/SDXL via pollinations.ai, no key needed
                        "huggingface"   → FREE, any HF Inference API model, optional token
                        "gemini_imagen" → Google Imagen 3/4, requires GEMINI_API_KEY
                       Default: "pollinations" (free, works out of the box)

    Storage backend:
      IMAGE_STORAGE_BACKEND — "local" (default), "s3", "gcs"
    """

    # ── Active provider ────────────────────────────────────────────────────────
    provider: str = os.getenv("IMAGE_PROVIDER", "pollinations")
    # ^ Change to "gemini_imagen" or "huggingface" in .env for production

    # ── Gemini Imagen settings ─────────────────────────────────────────────────
    # GEMINI_API_KEY is shared with the text generation config (ModelConfig)
    imagen_model: str = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
    # Alternative: "imagen-4.0-generate-preview-05-20"

    # ── Pollinations settings (FREE — no key needed) ───────────────────────────
    pollinations_model: str = os.getenv("POLLINATIONS_MODEL", "flux")
    # Options: "flux", "flux-pro", "flux-realism", "turbo", "dreamshaper", "any-dark"
    pollinations_timeout: int = int(os.getenv("POLLINATIONS_TIMEOUT", "90"))
    pollinations_seed: Optional[int] = (
        int(os.getenv("POLLINATIONS_SEED"))
        if os.getenv("POLLINATIONS_SEED", "").isdigit()
        else None
    )

    # ── Hugging Face settings (FREE with optional token) ───────────────────────
    hf_token: str = os.getenv("HF_TOKEN", "")
    hf_model: str = os.getenv("HF_MODEL", "black-forest-labs/FLUX.1-schnell")
    # Options: see imaging/providers/huggingface.py::HUGGINGFACE_FREE_MODELS
    hf_timeout: int = int(os.getenv("HF_TIMEOUT", "120"))

    # ── fal.ai settings (Recraft V3 & FLUX.1) ──────────────────────────────────
    fal_key: str = os.getenv("FAL_KEY", "")
    fal_model: str = os.getenv("FAL_MODEL", "fal-ai/recraft-v3")
    # Options: "fal-ai/recraft-v3", "fal-ai/flux/schnell", "fal-ai/flux-redux"

    # ── Storage settings ───────────────────────────────────────────────────────
    storage_backend: str = os.getenv("IMAGE_STORAGE_BACKEND", "local")
    # Local storage root — images saved to {local_storage_root}/{user_id}/{asset_id}.png
    local_storage_root: str = os.getenv("IMAGE_STORAGE_ROOT", "storage/images")

    # ── Job / worker settings ──────────────────────────────────────────────────
    image_queue_name: str = os.getenv("IMAGE_QUEUE_NAME", "trendforge-images")
    max_image_job_timeout: int = int(os.getenv("IMAGE_JOB_TIMEOUT", "300"))
    # Seconds before a stuck image job is considered failed


@dataclass
class ModelConfig:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model_small: str = os.getenv("GROQ_MODEL_SMALL", "openai/gpt-oss-20b")
    groq_model_large: str = os.getenv("GROQ_MODEL_LARGE", "openai/gpt-oss-120b")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    routing_temperature: float = 0.0
    generation_temperature: float = 0.85


@dataclass
class SourceConfig:
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")
    reddit_client_id: str = os.getenv("REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    reddit_user_agent: str = os.getenv("REDDIT_USER_AGENT", "TrendForge/1.0")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    enable_github: bool = os.getenv("ENABLE_GITHUB", "true").lower() == "true"
    enable_reddit: bool = os.getenv("ENABLE_REDDIT", "true").lower() == "true"
    enable_youtube: bool = os.getenv("ENABLE_YOUTUBE", "true").lower() == "true"
    enable_google_trends: bool = os.getenv("ENABLE_GOOGLE_TRENDS", "true").lower() == "true"
    enable_hackernews: bool = os.getenv("ENABLE_HACKERNEWS", "true").lower() == "true"
    enable_paperswithcode: bool = os.getenv("ENABLE_PAPERSWITHCODE", "true").lower() == "true"
    enable_huggingface: bool = os.getenv("ENABLE_HUGGINGFACE", "true").lower() == "true"
    enable_tavily: bool = os.getenv("ENABLE_TAVILY", "true").lower() == "true"


SOURCE_MAP = {
    "tech":          ["github", "reddit"],
    "business":      ["reddit", "google_trends", "tavily"],
    "lifestyle":     ["reddit", "youtube", "google_trends", "tavily"],
    "entertainment": ["reddit", "youtube", "google_trends", "tavily"],
    "education":     ["reddit", "youtube", "google_trends"],
    "news":          ["tavily", "google_trends"],
    "unknown":       ["google_trends", "reddit", "tavily"],
}


PLATFORM_SETTINGS = {
    "instagram": {
        "post_format": "image_caption", "max_caption_chars": 2200, "hashtag_count": 15,
        "tone": "aspirational, visual, lifestyle-driven", "hook_style": "bold statement or curiosity gap",
        "emoji_usage": "high",
    },
    "youtube": {
        "post_format": "video_script", "max_caption_chars": 5000, "hashtag_count": 10,
        "tone": "informative, engaging, educational", "hook_style": "question or surprising fact",
        "emoji_usage": "medium",
    },
    "linkedin": {
        "post_format": "professional_post", "max_caption_chars": 3000, "hashtag_count": 5,
        "tone": "professional, insightful, thought leadership", "hook_style": "bold insight or personal story",
        "emoji_usage": "low",
    },
    "tiktok": {
        "post_format": "short_video_script", "max_caption_chars": 2200, "hashtag_count": 10,
        "tone": "raw, authentic, Gen-Z, fast paced", "hook_style": "pattern interrupt, POV",
        "emoji_usage": "high",
    },
    "facebook": {
        "post_format": "community_post", "max_caption_chars": 5000, "hashtag_count": 3,
        "tone": "conversational, community-driven, relatable", "hook_style": "relatable statement or question",
        "emoji_usage": "medium",
    },
}

SUPPORTED_PLATFORMS = list(PLATFORM_SETTINGS.keys())


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


class TrendForgeConfig:
    def __init__(self):
        self.models = ModelConfig()
        self.sources = SourceConfig()
        self.system = SystemConfig()
        self.imaging = ImagingConfig()

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

        # Image provider validation
        provider = self.imaging.provider
        if provider == "gemini_imagen" and not self.models.gemini_api_key:
            warnings.append(
                "IMAGE_PROVIDER=gemini_imagen but GEMINI_API_KEY is missing. "
                "Image generation will fail. Falling back to mock."
            )
        elif provider == "huggingface" and not self.imaging.hf_token:
            warnings.append(
                "IMAGE_PROVIDER=huggingface but HF_TOKEN is not set. "
                "Requests will be severely rate-limited. "
                "Get a free token at https://huggingface.co/settings/tokens"
            )
        return warnings

    def available_sources(self) -> List[str]:
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


CONFIG = TrendForgeConfig()