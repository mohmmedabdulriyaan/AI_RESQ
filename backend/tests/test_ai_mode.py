"""Zero-budget guarantees: local analysis (ML + rules) by default, external AI only with explicit AI_MODE=llm."""
import httpx
import pytest

import ai

TEXT = "Our house is surrounded by floodwater. Four people are trapped, including an elderly person."


class Spy:
    def __init__(self):
        self.calls = 0

    def __call__(self, *a, **k):
        self.calls += 1
        raise AssertionError("external AI request must not happen in rules mode")


@pytest.fixture()
def keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    spy = Spy()
    monkeypatch.setattr(httpx, "post", spy)
    return spy


def test_default_mode_is_local_ml(monkeypatch):
    monkeypatch.delenv("AI_MODE", raising=False)
    assert ai.ai_mode() == "ml"


def test_keys_alone_do_not_enable_external_ai(monkeypatch, keys):
    monkeypatch.delenv("AI_MODE", raising=False)
    out = ai.analyze(TEXT)
    assert out["source"] == "ml" and keys.calls == 0


@pytest.mark.parametrize("mode,expected", [("rules", "rules"), ("RULES", "rules"), (" rules ", "rules"), ("ml", "ml"),
                                           ("auto", "ml"), ("", "ml"), ("llm2", "ml"), ("true", "ml"), ("on", "ml")])
def test_anything_but_explicit_llm_stays_local(monkeypatch, keys, mode, expected):
    monkeypatch.setenv("AI_MODE", mode)
    assert ai.ai_mode() == expected
    assert ai.analyze(TEXT)["source"] == expected
    assert keys.calls == 0


def test_llm_helper_refuses_in_rules_mode(monkeypatch, keys):
    monkeypatch.setenv("AI_MODE", "rules")
    with pytest.raises(RuntimeError):
        ai._llm(TEXT, None)
    assert keys.calls == 0


def test_rules_mode_through_api_makes_no_external_calls(client, monkeypatch, keys):
    monkeypatch.delenv("AI_MODE", raising=False)
    r = client.post("/api/reports", json={"type": "flood", "description": TEXT, "lat": 17.98, "lng": 79.59})
    assert r.status_code == 200 and r.json()["analysis"]["source"] == "ml"
    assert keys.calls == 0


def test_explicit_opt_in_uses_llm_with_mocked_api(monkeypatch):
    """Opt-in path still works. The HTTP call is mocked: no network, no cost."""
    monkeypatch.setenv("AI_MODE", "llm")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"content": [{"text": '{"category":"flood","priority_score":92,"people_affected":4,"vulnerable":["elderly"],'
                                          '"hazards":["trapped"],"recommended_team_type":"flood_rescue","summary":"Flood, 4 trapped."}'}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(a) or Resp())
    out = ai.analyze(TEXT)
    assert out["source"] == "llm" and out["priority"] == "Critical" and len(calls) == 1


def test_opt_in_without_key_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("AI_MODE", "llm")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert ai.analyze(TEXT)["source"] in ("ml", "rules")


def test_missing_scikit_learn_falls_back_to_rules(monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "ml":
            raise ImportError("No module named 'sklearn'")
        return real(name, *a, **k)
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake)
    out = ai.analyze(TEXT)
    assert out["source"] == "rules" and out["priority"] == "Critical"
