"""
web/test_conversation_history.py

Answers one specific question: across MULTIPLE separate HTTP requests to
the SAME session_id, does message_history actually accumulate correctly,
in order, and does it actually persist in Redis (not just survive because
it's still sitting in a Python variable somewhere)?

process_turn is monkeypatched here because exercising the real Groq call
needs a live API key this sandbox doesn't have -- but the fake mirrors
the real function's message_history side effects exactly (append user
turn, append assistant tool-call turn, append tool placeholder) so
finalize_turn's update_last_tool_result has real work to do, same as it
would against the real orchestrator.
"""
import fakeredis
import pytest
from fastapi.testclient import TestClient

import memory.redis_session_store as store
from web import app as app_module

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(store, "_client", fake)
    yield fake


def _fake_process_turn_factory(action_sequence):
    """Returns a process_turn stand-in that mirrors the REAL function's
    message_history writes turn by turn, cycling through action_sequence."""
    calls = {"i": 0}

    def _fake(conversation, message):
        conversation.setdefault("message_history", []).append({"role": "user", "content": message})
        action, args = action_sequence[calls["i"]]
        calls["i"] += 1
        call_id = f"call_{calls['i']}"
        conversation["message_history"].append({
            "role": "assistant", "content": "",
            "tool_calls": [{"id": call_id, "type": "function",
                            "function": {"name": action, "arguments": "{}"}}],
        })
        conversation["message_history"].append({
            "role": "tool", "tool_call_id": call_id, "content": f"dispatched:{action}",
        })
        return {"action": action, "args": args, "tokens_used": 5, "error": None}

    return _fake


def test_history_accumulates_correctly_across_three_separate_requests(monkeypatch):
    session_id = "sess-history-check"

    # Seed with existing posts so we're not forced through the stage-0
    # shortcut -- irrelevant here since we monkeypatch process_turn
    # anyway, but keeps this realistic.
    seeded = store._fresh_default()
    seeded["last_generated_posts"] = [{"title": "t1", "caption": "c1"}]
    store.save_conversation(session_id, seeded)

    fake = _fake_process_turn_factory([
        ("add_constraint", {"constraint_type": "exclude", "constraint_value": "n8n"}),
        ("add_constraint", {"constraint_type": "exclude", "constraint_value": "TensorFlow"}),
        ("remove_constraint", {"constraint_value": "n8n"}),
    ])
    monkeypatch.setattr(app_module, "process_turn", fake)

    # --- Turn 1 ---
    r1 = client.post("/chat", json={"message": "don't mention n8n", "session_id": session_id})
    assert r1.status_code == 200
    assert r1.json()["action"] == "add_constraint"

    # Reload directly from the store (bypassing the API entirely) to
    # prove this is really in Redis, not just held in a live variable.
    after_turn1 = store.load_conversation(session_id)
    assert len(after_turn1["message_history"]) == 3  # user, assistant, tool
    assert after_turn1["message_history"][0] == {"role": "user", "content": "don't mention n8n"}
    assert after_turn1["active_constraints"] == [{"type": "exclude", "value": "n8n"}]
    # tool placeholder must have been replaced with the REAL outcome by
    # update_last_tool_result, not left as "dispatched:add_constraint"
    tool_msg_1 = after_turn1["message_history"][2]
    assert tool_msg_1["role"] == "tool"
    assert "n8n" in tool_msg_1["content"]
    assert tool_msg_1["content"] != "dispatched:add_constraint"

    # --- Turn 2 (separate request, same session) ---
    r2 = client.post("/chat", json={"message": "also exclude TensorFlow", "session_id": session_id})
    assert r2.status_code == 200

    after_turn2 = store.load_conversation(session_id)
    assert len(after_turn2["message_history"]) == 6  # 2 full turns now
    assert after_turn2["message_history"][3] == {"role": "user", "content": "also exclude TensorFlow"}
    assert after_turn2["active_constraints"] == [
        {"type": "exclude", "value": "n8n"},
        {"type": "exclude", "value": "TensorFlow"},
    ]
    # Turn 1's history must still be intact, unmodified, at the front
    assert after_turn2["message_history"][0] == {"role": "user", "content": "don't mention n8n"}

    # --- Turn 3 (removes the first constraint) ---
    r3 = client.post("/chat", json={"message": "actually n8n is fine now", "session_id": session_id})
    assert r3.status_code == 200

    after_turn3 = store.load_conversation(session_id)
    assert len(after_turn3["message_history"]) == 9  # 3 full turns
    assert after_turn3["active_constraints"] == [{"type": "exclude", "value": "TensorFlow"}]
    # Full ordering across all 3 turns, end to end
    roles = [m["role"] for m in after_turn3["message_history"]]
    assert roles == ["user", "assistant", "tool"] * 3
    user_messages = [m["content"] for m in after_turn3["message_history"] if m["role"] == "user"]
    assert user_messages == [
        "don't mention n8n",
        "also exclude TensorFlow",
        "actually n8n is fine now",
    ]


def test_history_isolated_between_different_sessions(monkeypatch):
    """Two different session_ids talking 'at the same time' must never
    leak into each other -- this is the actual point of Phase 3."""
    fake_a = _fake_process_turn_factory([("add_constraint", {"constraint_type": "exclude", "constraint_value": "A-only"})])
    fake_b = _fake_process_turn_factory([("add_constraint", {"constraint_type": "exclude", "constraint_value": "B-only"})])

    for sid in ("sess-A", "sess-B"):
        seeded = store._fresh_default()
        seeded["last_generated_posts"] = [{"title": "t", "caption": "c"}]
        store.save_conversation(sid, seeded)

    monkeypatch.setattr(app_module, "process_turn", fake_a)
    client.post("/chat", json={"message": "for session A", "session_id": "sess-A"})

    monkeypatch.setattr(app_module, "process_turn", fake_b)
    client.post("/chat", json={"message": "for session B", "session_id": "sess-B"})

    sess_a = store.load_conversation("sess-A")
    sess_b = store.load_conversation("sess-B")

    assert sess_a["active_constraints"] == [{"type": "exclude", "value": "A-only"}]
    assert sess_b["active_constraints"] == [{"type": "exclude", "value": "B-only"}]
    assert len(sess_a["message_history"]) == 3
    assert len(sess_b["message_history"]) == 3
    assert sess_a["message_history"][0]["content"] == "for session A"
    assert sess_b["message_history"][0]["content"] == "for session B"