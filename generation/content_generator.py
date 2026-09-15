import html
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import TrendForgeState, add_log, add_error, add_tokens
from generation.prompt_composer import compose_prompt
from generation.prompts import SYSTEM_PROMPT
from Config.config import CONFIG
from llm.client import call_gemini, call_groq
from llm.errors import LLMCallFailed, LLMSchemaViolation
from llm.schemas import GeneratedPostsSchema


def _build_fallback_posts(state: TrendForgeState) -> list:
    posts = []
    fetched = state.get("fetched_data", {})
    topic = state.get("core_topic", "trending topics").strip()
    topic_title = topic.title()
    clean_tag = "".join(c for c in topic.lower() if c.isalnum()) or "techtrends"
    count = state.get("post_count", 5)
    content_intent = state.get("content_intent", "educate")

    # If real fetched items with meaningful descriptions exist and intent is showcase, use them
    valid_items = []
    for source, items in fetched.items():
        for item in items:
            title = item.get("title", item.get("name", "")).strip()
            desc = item.get("summary", item.get("description", item.get("snippet", ""))).strip()
            # Ignore search-engine query pages as item titles
            if title and not title.lower().startswith("tavily deep synthesis") and "search?q=" not in item.get("link", ""):
                valid_items.append((title, desc, item.get("link", "")))

    if content_intent == "showcase" and len(valid_items) >= count:
        for idx in range(count):
            title, desc, link = valid_items[idx]
            clean_t = html.unescape(title)
            clean_d = html.unescape(str(desc))
            posts.append({
                "number": idx + 1,
                "title": clean_t[:60],
                "hook": f"Why {clean_t[:40]} is making waves in {topic}",
                "summary": [
                    f"1. {clean_d[:70]}" if clean_d else f"1. Core feature of {clean_t[:30]}",
                    f"2. Built for modern {topic} workflows",
                    "3. Open source & community backed",
                ],
                "link": link,
                "caption": (
                    f"Exploring {clean_t} — a standout tool in {topic}.\n\n"
                    f"{clean_d[:200]}\n\n"
                    f"Have you worked with {clean_t}? Drop your thoughts below or save this post! 🔖"
                ),
                "hashtags": [f"#{clean_tag}", "#tech", "#innovation", "#developers", "#trends"],
            })
        return posts

    # Educational / Conceptual fallback: structured, high-signal carousel breakdown
    curriculum = [
        (
            f"Understanding {topic_title}",
            f"The foundations you need to master {topic}",
            [
                f"1. Core principles of {topic}",
                "2. Why modern teams care about this",
                "3. The primary problem it solves",
            ],
            (
                f"Mastering {topic} starts with understanding the core problems it addresses.\n\n"
                f"Whether building from scratch or scaling an existing system, the choices you make here "
                f"directly impact delivery speed, maintenance overhead, and scalability.\n\n"
                f"Save this guide to reference on your next sprint! 🔖"
            ),
        ),
        (
            f"Key Techniques in {topic_title}",
            "Different approaches compared for real-world use",
            [
                "1. Traditional monolithic patterns",
                "2. Modern distributed architectures",
                "3. Hybrid & modular compromises",
            ],
            (
                f"There is no one-size-fits-all approach to {topic}.\n\n"
                f"From straightforward single-unit structures to decoupled services, every pattern has "
                f"distinct trade-offs in complexity, reliability, and team autonomy.\n\n"
                f"Which approach has worked best for your stack?"
            ),
        ),
        (
            f"Trade-Offs & Complexity",
            "What you gain vs what you give up",
            [
                "1. Operational overhead vs velocity",
                "2. Debugging & observability challenges",
                "3. Infrastructure cost considerations",
            ],
            (
                f"Every architectural choice in {topic} comes with trade-offs.\n\n"
                f"Premature optimization often introduces distributed complexity before team size requires it. "
                f"Keep your structure as simple as possible until concrete scale demands otherwise.\n\n"
                f"Double tap if you've experienced this firsthand! 💡"
            ),
        ),
        (
            f"Best Practices for {topic_title}",
            "Rules senior engineers follow in production",
            [
                "1. Enforce strict domain boundaries",
                "2. Keep modules decoupled and testable",
                "3. Prioritize developer onboarding speed",
            ],
            (
                f"Pro tip for {topic}: design with clear boundaries from day one.\n\n"
                f"Even in a single codebase, keeping modules decoupled allows future migrations to happen "
                f"seamlessly without painful code rewrites.\n\n"
                f"Bookmark this checklist for code reviews! 📌"
            ),
        ),
        (
            f"Decision Framework for {topic_title}",
            "How to pick the right path for your next project",
            [
                "1. Evaluate team size and release velocity",
                "2. Measure domain & data complexity",
                "3. Choose the simplest model that scales",
            ],
            (
                f"Still deciding on the right approach to {topic}?\n\n"
                f"Ask these 3 questions: How big is the team? How fast do we need to ship? What are our scaling bottlenecks?\n\n"
                f"Which structure are you leaning toward? Comment below! 👇"
            ),
        ),
    ]

    for idx in range(min(count, len(curriculum))):
        title, hook, summary, caption = curriculum[idx]
        posts.append({
            "number": idx + 1,
            "title": title,
            "hook": hook,
            "summary": summary,
            "link": "",
            "caption": caption,
            "hashtags": [f"#{clean_tag}", "#softwarearchitecture", "#codingtips", "#programming", "#techinsights"],
        })

    return posts


class ContentGenerator:

    def generate(self, state: TrendForgeState) -> TrendForgeState:
        add_log(state, "[ContentGenerator] Starting generation cycle...")

        total_items = state.get("total_items_fetched", 0)
        fetched_data = state.get("fetched_data", {})
        add_log(state, f"[ContentGenerator] Processing {total_items} fetched items across {len(fetched_data)} sources")

        topic = state.get("core_topic", "")
        content_intent = state.get("content_intent", "showcase")

        all_items = []
        for source, items in state.get("fetched_data", {}).items():
            for item in items:
                item["_source"] = source
                all_items.append(item)

        target_count = state.get("post_count", 5)
        add_log(state, f"[ContentGenerator] Single-pass curation & generation — total_items={len(all_items)}, target_count={target_count}, intent={content_intent}")

        # Retain full pool in state for conversational refetch / add operations
        state["leftover_fetch_pool"] = list(all_items)

        prompt = compose_prompt(state)

        result = None
        engine_used = "None"

        try:
            add_log(state, f"[ContentGenerator] Sending generation instruction to {CONFIG.models.gemini_model}...")
            result = call_gemini(
                system=SYSTEM_PROMPT,
                user=prompt,
                model=CONFIG.models.gemini_model,
                schema=GeneratedPostsSchema,
                temperature=0.2,
            )
            engine_used = "Gemini"
        except (LLMCallFailed, LLMSchemaViolation) as gemini_error:
            add_tokens(state, "content_generation", getattr(gemini_error, "tokens_used", 0))
            add_error(state, f"[ContentGenerator] Gemini Service Alert: {gemini_error}")
            add_log(state, "[ContentGenerator] Rerouting operational prompt to Groq (LLaMA3) infrastructure...")
            try:
                result = call_groq(
                    system=SYSTEM_PROMPT,
                    user=prompt,
                    model=CONFIG.models.groq_model_large,
                    schema=GeneratedPostsSchema,
                    temperature=0.2,
                    reasoning_effort="low",
                )
                engine_used = "Groq-LLaMA3"
            except (LLMCallFailed, LLMSchemaViolation) as groq_error:
                add_tokens(state, "content_generation", getattr(groq_error, "tokens_used", 0))
                add_error(state, f"[ContentGenerator] Critical: Fallback engine failed: {groq_error}")

        validated = []
        if result is not None:
            add_log(state, f"[Generator] Raw payload validated successfully via {engine_used}.")
            add_tokens(state, "content_generation", result.tokens_used)
            raw_posts = result.content.get("posts", [])
            # Strip any accidental markdown headers or bold stars from card text
            import re
            def _clean_text(val):
                if not val:
                    return ""
                s = re.sub(r"^#+\s*", "", str(val))
                s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
                return s.strip()

            for p in raw_posts:
                if isinstance(p, dict):
                    if "title" in p:
                        p["title"] = _clean_text(p["title"])
                    if "hook" in p:
                        p["hook"] = _clean_text(p["hook"])
                    if "summary" in p and isinstance(p["summary"], list):
                        p["summary"] = [_clean_text(item) for item in p["summary"]]
                    validated.append(p)

        if not validated:
            add_log(state, "[ContentGenerator] System Warning: Engine output empty or failed validation — applying safe string builder.")
            validated = _build_fallback_posts(state)
            engine_used = "None"

        state["generated_posts"] = validated
        state["final_output"] = result.content.get("series_hook", "") if result else ""
        state["trend_insight"] = result.content.get("trend_insight", "") if result else ""
        state["content_generation_engine"] = engine_used

        add_log(state, f"[ContentGenerator] Execution ended. Generated {len(validated)} posts via {engine_used}.")
        return state