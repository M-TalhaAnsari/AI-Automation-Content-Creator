"""generation/platforms/registry.py -- Platform Strategy registry +
dispatcher. Pure Python dict lookup on state["platform"] -- NO LLM call
happens here. (The earlier understanding-layer LLM call in
understanding/intent_extractor.py is what reads the user's free text and
decides WHICH platform string to set; this registry only ever does a
string -> strategy lookup on that already-resolved value.)
"""
from generation.platforms.instagram_platform import InstagramPlatform
from generation.platforms.linkedin_platform import LinkedInPlatform
from generation.platforms.tiktok_platform import TikTokPlatform
from generation.platforms.youtube_platform import YouTubePlatform
from generation.platforms.facebook_platform import FacebookPlatform

PLATFORM_STRATEGY_MAP = {
    "instagram": InstagramPlatform(),
    "linkedin": LinkedInPlatform(),
    "tiktok": TikTokPlatform(),
    "youtube": YouTubePlatform(),
    "facebook": FacebookPlatform(),
}


def get_platform_strategy(platform: str):
    return PLATFORM_STRATEGY_MAP.get(platform, PLATFORM_STRATEGY_MAP["instagram"])