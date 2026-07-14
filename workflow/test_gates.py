"""
workflow/test_gates.py — standalone verification for gates.py

Hand-constructs fake TrendForgeState dicts, no pipeline run needed.
Run directly: python workflow/test_gates.py
Delete after manual verification if not kept as a permanent test.
"""

from workflow.gates import evaluate_fetch_quality, evaluate_post_validation

passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}")


def base_state(**overrides):
    state = {
        "total_items_fetched": 10,
        "sources_used": ["github", "tavily"],
        "fetch_retry_count": 0,
        "search_queries": ["query A", "query B", "query C"],
        "generated_posts": [],
        "platform": "instagram",
        "content_intent": "showcase",
        "data_starved": False,
        "generation_retry_count": 0,
    }
    state.update(overrides)
    return state


def good_post(**overrides):
    post = {
        "title": "Unique Title",
        "hook": "A hook",
        "caption": "A caption of reasonable length.",
        "summary": ["point one", "point two"],
        "hashtags": ["#tag1", "#tag2"],
        "link": "https://example.com/repo",
    }
    post.update(overrides)
    return post


# ── evaluate_fetch_quality ──────────────────────────────────

print("evaluate_fetch_quality:")

r = evaluate_fetch_quality(base_state(total_items_fetched=10, sources_used=["github"]))
check("sufficient data passes", r["sufficient"] is True)

r = evaluate_fetch_quality(base_state(total_items_fetched=0, sources_used=[]))
check("zero items flagged insufficient", r["sufficient"] is False)
check("zero items allows retry (under cap)", r["should_retry"] is True)
check("zero items cycles to search_queries[1]", r["next_query"] == "query B")

r = evaluate_fetch_quality(base_state(total_items_fetched=2, sources_used=["github"], fetch_retry_count=2))
check("insufficient data past retry cap stops retrying", r["should_retry"] is False)

r = evaluate_fetch_quality(base_state(total_items_fetched=50, sources_used=[]))
check("items present but no source in sources_used is still insufficient", r["sufficient"] is False)

r = evaluate_fetch_quality(base_state(
    total_items_fetched=10, sources_used=["google_trends"], content_intent="showcase",
    fetched_data={"google_trends": [
        {"link": "https://www.google.com/search?q=machine+learning+projects"},
        {"link": "https://www.google.com/search?q=machine+learning+github"},
    ]}
))
check("enough items but all links are generic search URLs — caught for showcase intent (real thrashing bug found in production)",
      r["sufficient"] is False)

r = evaluate_fetch_quality(base_state(
    total_items_fetched=10, sources_used=["google_trends"], content_intent="educate",
    fetched_data={"google_trends": [{"link": "https://www.google.com/search?q=docker"}]}
))
check("all-search-URL links NOT flagged for educate intent (links are optional there)", r["sufficient"] is True)

r = evaluate_fetch_quality(base_state(total_items_fetched=0, sources_used=[], fetch_retry_count=0,
                                       search_queries=["only one query"]))
check("exhausted query variants reuses last instead of erroring", r["next_query"] == "only one query")

# ── evaluate_post_validation ────────────────────────────────

print("\nevaluate_post_validation:")

r = evaluate_post_validation(base_state(generated_posts=[good_post()]))
check("well-formed post passes", r["valid"] is True)

r = evaluate_post_validation(base_state(generated_posts=[good_post(hook="")]))
check("missing hook caught", any("hook" in e for e in r["errors"]))

r = evaluate_post_validation(base_state(generated_posts=[good_post(summary=[])]))
check("empty summary list caught", any("summary" in e for e in r["errors"]))

r = evaluate_post_validation(base_state(content_intent="showcase", generated_posts=[good_post(link="")]))
check("missing link caught for showcase intent", any("link" in e for e in r["errors"]))

r = evaluate_post_validation(base_state(content_intent="showcase",
                                         generated_posts=[good_post(link="https://www.google.com/search?q=machine+learning+projects")]))
check("generic Google search URL rejected for showcase intent (real bug found in forced-failure test run)",
      any("search-engine" in e for e in r["errors"]))

r = evaluate_post_validation(base_state(content_intent="educate",
                                         generated_posts=[good_post(link="https://www.bing.com/search?q=docker")]))
check("generic search URL NOT flagged for educate intent (link is optional there, empty preferred over fake but not an error)",
      r["valid"] is True)

r = evaluate_post_validation(base_state(content_intent="educate", generated_posts=[good_post(link="")]))
check("missing link allowed for educate intent", r["valid"] is True)

r = evaluate_post_validation(base_state(content_intent="showcase", data_starved=True,
                                         generated_posts=[good_post(link="")]))
check("data_starved overrides showcase's link requirement", r["valid"] is True)

r = evaluate_post_validation(base_state(platform="instagram",
                                         generated_posts=[good_post(caption="x" * 3000)]))
check("caption over platform limit caught", any("exceeds" in e for e in r["errors"]))

r = evaluate_post_validation(base_state(generated_posts=[good_post(title="Same Title"), good_post(title="Same Title")]))
check("duplicate titles across batch caught", any("duplicate" in e for e in r["errors"]))

r = evaluate_post_validation(base_state(generated_posts=[good_post(hook="")], generation_retry_count=2))
check("invalid post past retry cap stops retrying", r["should_retry"] is False)

print(f"\n{passed} passed, {failed} failed")