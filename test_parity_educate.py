# test_parity_educate.py — throwaway script, delete after
from main import run
from workflow.graph import run_graph

# Deliberately phrased to trigger content_intent="educate" per
# intent_extractor.py's classification rules — same pattern you've
# already tested manually with "docker key concepts" prompts.
prompt = "explain docker core concepts for interview prep on instagram"

old = run(prompt)
new = run_graph(prompt)

print("OLD keys:", sorted(old.keys()))
print("NEW keys:", sorted(new.keys()))
assert sorted(old.keys()) == sorted(new.keys()), "KEY MISMATCH — the 9-key contract broke"

for k in ["session_id", "topic", "platform", "content_intent"]:
    print(f"{k}: old={old.get(k)!r} | new={new.get(k)!r}")

# The real point of this scenario: confirm content_intent actually landed
# on "educate" for both paths, not just that the keys match generically.
assert old.get("content_intent") == "educate", f"OLD path did not classify as educate — got {old.get('content_intent')!r}"
assert new.get("content_intent") == "educate", f"NEW path did not classify as educate — got {new.get('content_intent')!r}"

print(f"OLD posts: {len(old.get('posts', []))}")
print(f"NEW posts: {len(new.get('posts', []))}")
print(f"OLD errors: {old.get('errors')}")
print(f"NEW errors: {new.get('errors')}")

print("\n✅ Educate-intent parity check complete.")