"""
conversation/test_actions.py — standalone verification for actions.py
Run directly: python conversation/test_actions.py
"""
import sys, types, json

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

FAKE_POSTS = [
    {"title": f"Post {i}", "hook": f"hook{i}", "caption": f"cap{i}",
     "summary": ["s"], "link": "https://x.com", "hashtags": ["#t"]}
    for i in range(1, 6)
]

# ── Mock google.genai before importing actions.py ──────────────────
genai_call_log = []

def install_fake_genai(edited_posts):
    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")

    class FakeResponse:
        text = json.dumps({"posts": edited_posts})
        class usage_metadata:
            total_token_count = 42

    class FakeModels:
        def generate_content(self, model, contents):
            genai_call_log.append(contents)
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    genai_mod.Client = FakeClient
    google_mod.genai = genai_mod
    sys.modules["google"] = google_mod
    sys.modules["google.genai"] = genai_mod

install_fake_genai([{"title": "EDITED", "hook": "h", "caption": "c", "summary": ["s"], "link": "https://x.com", "hashtags": ["#t"]}])

# ── Stub config, core.state, generation.content_generator, workflow.gates, fetchers ──
config_mod = types.ModuleType("config")
config_mod.CONFIG = types.SimpleNamespace(models=types.SimpleNamespace(gemini_api_key="fake", gemini_model="gemini-2.0-flash"))
sys.modules["config"] = config_mod

def _parse_json(text):
    try:
        return json.loads(text)
    except Exception:
        return {}

gen_mod = types.ModuleType("generation")
sys.modules["generation"] = gen_mod
cg_mod = types.ModuleType("generation.content_generator")
cg_mod._parse_json = _parse_json
sys.modules["generation.content_generator"] = cg_mod

gates_mod = types.ModuleType("workflow.gates")
MIN_FLOOR = 3
def evaluate_fetch_quality(state):
    total = state.get("total_items_fetched", 0)
    has_source = len(state.get("sources_used", [])) > 0
    return {"sufficient": total >= MIN_FLOOR and has_source, "reason": "", "should_retry": False, "next_query": None}
gates_mod.evaluate_fetch_quality = evaluate_fetch_quality
workflow_mod = types.ModuleType("workflow")
sys.modules["workflow"] = workflow_mod
sys.modules["workflow.gates"] = gates_mod

fetch_orch_call_log = []
class FakeFetcherOrchestrator:
    def fetch(self, state):
        fetch_orch_call_log.append(state)
        state["fetched_data"] = {"tavily": [{"title": "new item", "link": "https://real.com"}]}
        return state
fetchers_mod = types.ModuleType("fetchers")
sys.modules["fetchers"] = fetchers_mod
fo_mod = types.ModuleType("fetchers.fetcher_orchestrator")
fo_mod.FetcherOrchestrator = FakeFetcherOrchestrator
sys.modules["fetchers.fetcher_orchestrator"] = fo_mod

import importlib.util
spec = importlib.util.spec_from_file_location("conversation.actions", "conversation/actions.py")
actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions)

# ── Tests ────────────────────────────────────────────────────────

print("edit_existing:")
result = actions.edit_existing([2], "make it shorter", FAKE_POSTS)
check("targeting [2] only changes post index 1 (0-based)", result["edited_posts"][1]["title"] == "EDITED")
check("targeting [2] leaves other posts untouched", result["edited_posts"][0]["title"] == "Post 1")
check("tokens_used populated", result["tokens_used"] == 42)

install_fake_genai([{"title": f"EDITED{i}", "hook": "h", "caption": "c", "summary": ["s"], "link": "https://x.com", "hashtags": ["#t"]} for i in range(5)])
result_all = actions.edit_existing("all", "make it shorter", FAKE_POSTS)
check("targeting 'all' changes every post", all(p["title"].startswith("EDITED") for p in result_all["edited_posts"]))

print("\nadd_constraint:")
r1 = actions.add_constraint("exclude", "tensorflow", [])
r2 = actions.add_constraint("exclude", "tensorflow", r1["active_constraints"])
check("duplicate add is a no-op", len(r2["active_constraints"]) == 1)

r3 = actions.add_constraint("weird_type", "docker", [])
check("invalid constraint_type defaults to exclude", r3["active_constraints"][0]["type"] == "exclude")

print("\nremove_constraint:")
r4 = actions.remove_constraint("tensorflow", r1["active_constraints"])
check("removes matching constraint", len(r4["active_constraints"]) == 0)
r5 = actions.remove_constraint("not_present", r1["active_constraints"])
check("removing absent value is a no-op, not an error", len(r5["active_constraints"]) == 1)

print("\ntargeted_refetch:")    
fetch_orch_call_log.clear()
sufficient_pool = [{"title": f"item{i}", "summary": "", "_source": "tavily"} for i in range(5)]
r6 = actions.targeted_refetch("broaden", "machine learning", sufficient_pool, [])
check("sufficient leftover pool returns without triggering new fetch", r6["used_leftover_pool"] is True)
check("fetcher_orchestrator NOT called when pool is sufficient", len(fetch_orch_call_log) == 0)

fetch_orch_call_log.clear()
insufficient_pool = [{"title": "item1", "summary": "", "_source": "tavily"}]
r7 = actions.targeted_refetch("broaden", "machine learning", insufficient_pool, [])
check("insufficient pool triggers real fetch path", len(fetch_orch_call_log) == 1)
check("used_leftover_pool is False when a real fetch happened", r7["used_leftover_pool"] is False)

exclude_pool = [{"title": "tensorflow project", "summary": "", "_source": "tavily"}] * 5
r8 = actions.targeted_refetch("broaden", "ml", exclude_pool, [{"type": "exclude", "value": "tensorflow"}])
check("exclude constraint filters matching items out of the pool", len(fetch_orch_call_log) == 2)  # triggered again since filtered pool is empty

print(f"\n{passed} passed, {failed} failed")