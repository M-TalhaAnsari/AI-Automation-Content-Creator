"""
imaging/brief_builder.py — Constructs structured ContentBrief and VisualBrief objects.

Design Intent:
─────────────
Content generation must distinguish between:
  A. User requirements & explicit facts
  B. Content topic & concepts
  C. Platform rules
  D. Tone & audience
  E. Brand visual direction

This module is the single place where raw post data, platform constraints, and
brand visual profiles are assembled into a structured VisualBrief.

It does NOT assemble the raw prompt string (that is prompt_builder.py's job).
This clean separation allows:
  1. Inspecting and debugging the visual concept before sending it to an AI model.
  2. Modifying brand visual profiles without breaking prompt structure.
  3. Re-targeting the same content brief for different platforms/providers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from imaging.models import (
    BrandVisualProfile,
    ContentBrief,
    ContentTone,
    LayoutType,
    VisualBrief,
)

# ─────────────────────────────────────────────────────────────────────────────
# Platform-Specific Visual Rules
# ─────────────────────────────────────────────────────────────────────────────

PLATFORM_VISUAL_RULES: Dict[str, Dict[str, Any]] = {
    "instagram": {
        "aspect_ratio": "4:5",               # Portrait (1080x1350)
        "default_layout": LayoutType.TEXT_CARD,
        "max_text_overlay_words": 10,
        "visual_priority": "clean_hierarchy", # High readability, strong typographic hierarchy
        "supports_portrait": True,
        "supports_carousel": True,
        "avoid": ["tiny illegible code", "excessive emojis", "cluttered borders"],
    },
    "youtube": {
        "aspect_ratio": "16:9",              # Landscape thumbnail (1280x720)
        "default_layout": LayoutType.THUMBNAIL,
        "max_text_overlay_words": 6,
        "visual_priority": "high_contrast",  # Large bold focal point, immediate recognition
        "supports_portrait": False,
        "supports_carousel": False,
        "avoid": ["dense text paragraphs", "subtle low-contrast backgrounds"],
    },
    "linkedin": {
        "aspect_ratio": "1:1",               # Square or 4:5
        "default_layout": LayoutType.MINIMAL_CLEAN,
        "max_text_overlay_words": 12,
        "visual_priority": "professional_insight",
        "supports_portrait": True,
        "supports_carousel": True,
        "avoid": ["cartoonish graphics", "overly dramatic clickbait imagery"],
    },
    "tiktok": {
        "aspect_ratio": "9:16",              # Fullscreen vertical
        "default_layout": LayoutType.BOLD_CONTRAST,
        "max_text_overlay_words": 8,
        "visual_priority": "fast_paced_hook",
        "supports_portrait": True,
        "supports_carousel": False,
        "avoid": ["small unreadable text", "static corporate diagrams"],
    },
    "facebook": {
        "aspect_ratio": "1:1",
        "default_layout": LayoutType.MINIMAL_CLEAN,
        "max_text_overlay_words": 10,
        "visual_priority": "community_friendly",
        "supports_portrait": True,
        "supports_carousel": True,
        "avoid": ["dense complex diagrams"],
    },
}

DEFAULT_PLATFORM_RULES = {
    "aspect_ratio": "1:1",
    "default_layout": LayoutType.MINIMAL_CLEAN,
    "max_text_overlay_words": 10,
    "visual_priority": "informative",
    "supports_portrait": True,
    "supports_carousel": False,
    "avoid": ["generic clipart", "watermarks", "low resolution"],
}


def _extract_technical_keywords(text: str) -> List[str]:
    """Identify key technical names, tools, languages, and frameworks in text."""
    known_tech = [
        "python", "docker", "kubernetes", "langchain", "langgraph", "rag",
        "fastapi", "react", "postgresql", "redis", "qdrant", "chromadb",
        "pinecone", "llamaIndex", "gpt-4", "gemini", "claude", "pytorch",
        "tensorflow", "huggingface", "pydantic", "aws", "gcp", "azure",
        "linux", "graphql", "rest api", "grpc", "git", "github", "rust",
        "typescript", "go", "kafka", "pandas", "numpy", "crewai", "autogen",
    ]
    text_lower = text.lower()
    found = []
    for tech in known_tech:
        # Match whole word
        if re.search(r"\b" + re.escape(tech) + r"\b", text_lower):
            found.append(tech.title() if len(tech) > 3 else tech.upper())
    return found


def build_content_brief(
    post_data: Dict[str, Any],
    platform: str = "instagram",
    post_number: int = 1,
) -> ContentBrief:
    """
    Extracts a structured ContentBrief from post data.

    Preserves explicit technical facts, keywords, and tone without losing
    user intent during transformation.
    """
    title = str(post_data.get("title") or f"Post {post_number}").strip()
    topic = str(post_data.get("topic") or post_data.get("core_topic") or title).strip()
    subtitle = str(post_data.get("hook") or "").strip()

    # Extract summary points
    summary_raw = post_data.get("summary") or []
    if isinstance(summary_raw, str):
        key_concepts = [s.strip().lstrip("•-📌 ") for s in summary_raw.split("\n") if s.strip()]
    elif isinstance(summary_raw, list):
        key_concepts = [str(s).strip().lstrip("•-📌 ") for s in summary_raw if str(s).strip()]
    else:
        key_concepts = []

    caption = str(post_data.get("caption") or "")
    combined_text = f"{title} {subtitle} {' '.join(key_concepts)} {caption}"

    # Extract technical elements from all fields
    technical_elements = _extract_technical_keywords(combined_text)

    # Determine intent and tone
    content_intent = str(post_data.get("content_intent") or "showcase")
    tone = ContentTone.INFORMATIVE
    if content_intent in ("showcase", "educate"):
        tone = ContentTone.TECHNICAL
    elif content_intent == "inspire":
        tone = ContentTone.INSPIRATIONAL

    source_url = str(post_data.get("link") or post_data.get("sourceUrl") or post_data.get("url") or "")
    source_label = str(post_data.get("sourceLabel") or post_data.get("_source") or "")

    return ContentBrief(
        topic=topic,
        title=title,
        subtitle=subtitle if subtitle else None,
        key_concepts=key_concepts[:4],
        technical_elements=technical_elements[:6],
        key_facts=[],
        content_intent=content_intent,
        tone=tone,
        audience="developers, engineers, and tech creators",
        source_url=source_url or None,
        source_label=source_label or None,
        platform=platform.lower(),
        post_number=post_number,
    )


def build_visual_brief(
    content_brief: ContentBrief,
    profile: Optional[BrandVisualProfile] = None,
    platform: Optional[str] = None,
) -> VisualBrief:
    """
    Combines ContentBrief + Platform Rules + Brand Profile into a VisualBrief.

    Determines layout type, aspect ratio, text overlays, and styling directions.
    """
    resolved_platform = (platform or content_brief.platform).lower()
    platform_rules = PLATFORM_VISUAL_RULES.get(resolved_platform, DEFAULT_PLATFORM_RULES)

    # Apply platform override from brand profile if available
    effective_profile = profile.for_platform(resolved_platform) if profile else None

    # Resolve aspect ratio
    aspect_ratio = platform_rules["aspect_ratio"]
    override = effective_profile.platform_overrides.get(resolved_platform) if effective_profile else None
    if override and override.aspect_ratio:
        aspect_ratio = override.aspect_ratio

    # Resolve layout archetype
    if effective_profile and effective_profile.default_layout:
        layout_type = effective_profile.default_layout
    else:
        layout_type = platform_rules["default_layout"]

    # Select visual mood
    visual_mood = effective_profile.visual_mood if effective_profile else "clean-informative"

    # Determine text overlay on image (only when meaningful)
    max_words = platform_rules["max_text_overlay_words"]
    if override and override.max_text_overlay_words:
        max_words = override.max_text_overlay_words

    title_words = content_brief.title.split()
    if len(title_words) <= max_words:
        text_overlay_title = content_brief.title
    else:
        text_overlay_title = " ".join(title_words[:max_words]) + "..."

    # Formulate color direction
    if effective_profile and effective_profile.color_palette:
        cp = effective_profile.color_palette
        color_direction = (
            f"Dominant background: {cp.primary}, secondary tone: {cp.secondary}, "
            f"vibrant highlight accent: {cp.accent}, text: {cp.text}"
        )
    else:
        color_direction = "Dark modern tech palette (deep navy/slate #1a1a2e) with electric coral/cyan accent"

    # Build emphasis elements
    emphasis = []
    if content_brief.technical_elements:
        emphasis.extend([f"Icon/symbol of {tech}" for tech in content_brief.technical_elements[:3]])
    if content_brief.key_concepts:
        emphasis.append(f"Visual concept representing {content_brief.key_concepts[0]}")

    # Build avoid elements
    avoid = list(platform_rules.get("avoid", []))
    avoid.extend([
        "generic cartoon clip art",
        "chaotic decorative doodles",
        "distorted text characters",
        "busy unreadable backgrounds",
    ])

    return VisualBrief(
        content_brief=content_brief,
        visual_mood=visual_mood,
        layout_type=layout_type,
        color_direction=color_direction,
        text_overlay_title=text_overlay_title,
        text_overlay_subtitle=content_brief.subtitle if len((content_brief.subtitle or "").split()) <= 8 else None,
        include_source_label=bool(content_brief.source_label),
        max_text_overlay_words=max_words,
        emphasis_elements=emphasis,
        avoid_elements=avoid,
        aspect_ratio=aspect_ratio,
        platform_constraints=platform_rules,
        visual_profile_id=effective_profile.id if effective_profile else None,
    )
