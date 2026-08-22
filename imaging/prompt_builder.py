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
            "Premium social media tech showcase graphic, modern glassmorphism container with subtle glowing neon borders, "
            "vibrant futuristic 3D tech icons and isometric badges, sleek dark obsidian slate background, "
            "editorial Dribbble design, trending on Behance, dramatic studio backlighting, ultra-detailed 8k render"
        ),
        LayoutType.DIAGRAM: (
            "Clean futuristic system architecture visualization, glowing isometric data nodes, laser flow paths, "
            "holographic tech interface elements, blueprint style on dark carbon fiber backdrop, ultra-sharp vector details"
        ),
        LayoutType.MINIMAL_CLEAN: (
            "High-end tech brand visual identity, central glowing 3D geometric abstract asset, deep midnight blue background, "
            "soft ambient volumetric light, elegant visual hierarchy, Apple keynote style presentation visual"
        ),
        LayoutType.BOLD_CONTRAST: (
            "High-contrast dynamic tech visual, striking electric cyan and deep violet duotone accents, "
            "cyberpunk minimalist aesthetic, dramatic edge lighting, bold futuristic composition"
        ),
        LayoutType.THUMBNAIL: (
            "High-impact YouTube thumbnail composition, cinematic central 3D focal element, "
            "bold vibrant depth, studio lighting, crisp edges, glowing volumetric light, high CTR style"
        ),
        LayoutType.PHOTO_REALISTIC: (
            "Modern developer setup photography, sleek ultra-wide monitors displaying glowing code and system telemetry, "
            "cozy ambient neon lighting, clean wooden desk, cinematic bokeh depth of field, 8k resolution"
        ),
        LayoutType.ABSTRACT_TECH: (
            "Abstract neural network visualization, glowing synapses and flowing cybernetic data streams, "
            "sophisticated dark slate background with electric cyan, emerald and violet accents, octane render"
        ),
        LayoutType.INFORMATIVE_INFOGRAPHIC: (
            "High-end technology roadmap infographic visual, 3D floating sequential milestone platforms, "
            "glowing pipeline connectors, futuristic dashboard aesthetic, crisp vector elements, ultra-detailed 4k"
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
