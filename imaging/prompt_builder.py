"""
imaging/prompt_builder.py — Generates provider-tuned Image Generation Prompts from VisualBriefs.

Design Intent:
─────────────
Transforms a structured VisualBrief into natural-language prompts.
Does NOT simply concatenate the post's text. Instead, it crafts a prompt
tailored to the layout archetype (text card, architectural diagram, minimal graphic,
or thumbnail) and platform constraints.

Generates both:
  1. Main positive prompt
  2. Negative prompt (exclusions)
"""

from __future__ import annotations

from typing import Tuple

from imaging.models import LayoutType, VisualBrief


def _build_layout_prompt_chunk(layout: LayoutType) -> str:
    """Provides style and composition phrasing based on the layout archetype."""
    mapping = {
        LayoutType.TEXT_CARD: (
            "Modern minimalist UI card design, sleek typography layout, crisp vector geometric accents, "
            "ample negative space, clean grid structure, dark mode aesthetic"
        ),
        LayoutType.DIAGRAM: (
            "Clean technical architecture diagram, isometric system components, connecting data flows, "
            "minimalist node structure, blueprint style, precise vector lines"
        ),
        LayoutType.MINIMAL_CLEAN: (
            "Ultra-clean minimalist graphic illustration, elegant typography focal point, generous whitespace, "
            "subtle modern gradient, high-end editorial tech design"
        ),
        LayoutType.BOLD_CONTRAST: (
            "High-contrast dynamic graphic, bold typographic focal point, striking dual-tone color accents, "
            "dramatic lighting, modern cyber-minimalist vibe"
        ),
        LayoutType.THUMBNAIL: (
            "High-impact YouTube thumbnail composition, high contrast, prominent central focal element, "
            "bold vibrant depth, studio lighting, crisp edges"
        ),
        LayoutType.PHOTO_REALISTIC: (
            "Modern developer workspace photography, sleek laptop terminal on wooden desk, moody ambient lighting, "
            "cinematic depth of field, 8k resolution"
        ),
        LayoutType.ABSTRACT_TECH: (
            "Abstract geometric data visualization, glowing network nodes, subtle cybernetic patterns, "
            "sophisticated dark slate background with neon accents"
        ),
        LayoutType.INFORMATIVE_INFOGRAPHIC: (
            "Clean technical infographic layout, structured sequential steps, modern iconography, "
            "clear hierarchy, vector quality"
        ),
    }
    return mapping.get(layout, mapping[LayoutType.MINIMAL_CLEAN])


def build_image_prompt(visual_brief: VisualBrief) -> Tuple[str, str]:
    """
    Constructs a positive and negative prompt tuple from a VisualBrief.

    Returns:
        (positive_prompt, negative_prompt)
    """
    content = visual_brief.content_brief

    # 1. Subject Description
    subject_parts = []
    if content.title:
        subject_parts.append(f"Technical illustration for '{content.title}'")
    if content.topic:
        subject_parts.append(f"Theme: {content.topic}")

    if content.technical_elements:
        tech_list = ", ".join(content.technical_elements[:4])
        subject_parts.append(f"featuring concepts of {tech_list}")
    elif content.key_concepts:
        concepts_list = ", ".join(content.key_concepts[:2])
        subject_parts.append(f"illustrating {concepts_list}")

    subject_phrase = ". ".join(subject_parts)

    # 2. Composition & Layout
    layout_phrase = _build_layout_prompt_chunk(visual_brief.layout_type)

    # 3. Mood & Palette
    mood_phrase = f"Mood: {visual_brief.visual_mood}. Palette: {visual_brief.color_direction}"

    # 4. Emphasis elements
    emphasis_phrase = ""
    if visual_brief.emphasis_elements:
        emphasis_phrase = f"Key elements: {', '.join(visual_brief.emphasis_elements[:3])}."

    # 5. Framing / Quality parameters
    quality_phrase = (
        "Professional digital graphic design, vector-sharp lines, pristine quality, "
        "sophisticated tech aesthetic, 4k render, no blur."
    )

    # Assemble full positive prompt
    prompt_chunks = [
        subject_phrase,
        layout_phrase,
        mood_phrase,
    ]
    if emphasis_phrase:
        prompt_chunks.append(emphasis_phrase)
    prompt_chunks.append(quality_phrase)

    positive_prompt = ". ".join(chunk.strip(" .") for chunk in prompt_chunks if chunk) + "."

    # Assemble negative prompt
    base_negatives = [
        "blurry",
        "low resolution",
        "pixelated",
        "distorted text",
        "garish neon oversaturation",
        "unnecessary emojis",
        "childish cartoon",
        "watermarks",
        "signatures",
        "cluttered messy background",
        "ugly framing",
        "deformed shapes",
    ]
    if visual_brief.avoid_elements:
        base_negatives.extend(visual_brief.avoid_elements)

    # Deduplicate while preserving order
    seen = set()
    unique_negatives = []
    for item in base_negatives:
        clean = item.strip().lower()
        if clean not in seen:
            seen.add(clean)
            unique_negatives.append(clean)

    negative_prompt = ", ".join(unique_negatives)

    return positive_prompt, negative_prompt
