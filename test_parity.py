# test_parity.py — throwaway script, delete after
from main import run
from workflow.graph import run_graph

prompt = "top 5 machine learning projects for instagram"

old = run(prompt)
new = run_graph(prompt)

print("OLD keys:", sorted(old.keys()))
print("NEW keys:", sorted(new.keys()))
assert sorted(old.keys()) == sorted(new.keys()), "KEY MISMATCH — the 9-key contract broke"

for k in ["session_id", "topic", "platform", "content_intent"]:
    print(f"{k}: old={old.get(k)!r} | new={new.get(k)!r}")

print(f"OLD posts: {len(old.get('posts', []))}")
print(f"NEW posts: {len(new.get('posts', []))}")

# Previously missing — needed to catch silent divergence in fallback
# behavior (e.g. Gemini quota errors being handled differently between
# the two paths without either path crashing).
print(f"OLD errors: {old.get('errors')}")
print(f"NEW errors: {new.get('errors')}")

print("\n✅ Showcase parity check complete.")