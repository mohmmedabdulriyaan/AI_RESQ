"""Local scikit-learn classifier + rule safety net."""
import pytest

import ml
from ai import analyze, rule_analyze


@pytest.fixture(autouse=True)
def ml_mode(monkeypatch):
    monkeypatch.setenv("AI_MODE", "ml")


@pytest.mark.parametrize("text,priority,team", [
    ("Our house is surrounded by floodwater. Four people are trapped, including an elderly person.", "Critical", "flood_rescue"),
    ("A tree has fallen across the road, blocking vehicle movement.", "High", "road_clearance"),
    ("We need drinking water and food supplies at our location.", "Moderate", "relief_supply"),
])
def test_brief_scenarios(text, priority, team):
    a = analyze(text)
    assert a["source"] == "ml" and a["priority"] == priority and a["recommended_team_type"] == team


def test_output_has_same_contract_as_rules():
    a, r = analyze("Fire in the shop, smoke everywhere"), rule_analyze("Fire in the shop, smoke everywhere")
    assert set(r) <= set(a)
    assert a["needs_human_review"] is True
    assert a["reasons"][0].startswith("ML classifier")
    assert 0 <= a["ml"]["priority_confidence"] <= 1


def test_life_threat_signal_always_critical():
    # whatever the classifier thinks, explicit life-threat words keep the Critical floor
    for t in ["he is not breathing", "a man is unconscious near the shop", "someone is trapped in the lift"]:
        assert analyze(t)["priority"] == "Critical", t


def test_safe_report_stays_low_and_keeps_category():
    a = analyze("There is no fire here, everyone is safe.")
    assert a["priority"] == "Low" and a["category"] != "fire"


def test_never_lower_than_rules():
    for t in ["Two people injured in a crash. Help needed.", "Water is rising in our colony", "Need blankets for 3 families"]:
        assert analyze(t)["priority_score"] >= rule_analyze(t)["priority_score"]


def test_classifier_covers_reports_without_rule_keywords():
    # no rule keyword here; the classifier should still route it sensibly
    a = analyze("The lift is stuck between floors with four people inside")
    assert a["category"] in ("other", "medical") and a["priority"] in ("High", "Critical")




def test_confident_classifier_overrides_default_dropdown_type():
    # reporter left the type dropdown on its default "flood"; nothing in the text is about water
    a = analyze("The lift is stuck between floors with four people inside", "flood")
    assert a["category"] != "flood"


def test_rule_keywords_beat_classifier_category():
    a = analyze("Fire in the godown", "flood")
    assert a["category"] == "fire"


# ---- P1 regressions (dev-set examples; fixed with general rules, not by training on them) ----
def test_family_stranded_on_roof_with_rising_water():
    a = analyze("Family of five stuck on the roof, water still rising, baby with us")
    assert a["priority"] == "Critical" and a["category"] == "flood" and a["recommended_team_type"] == "flood_rescue"
    assert a["people_affected"] == 5


def test_labour_during_flood_is_medical_with_flood_rescue_as_secondary():
    a = analyze("Pregnant woman in labour, roads flooded, cannot reach hospital")
    assert a["category"] == "medical" and a["recommended_team_type"] == "medical_response"
    assert a["secondary_team_type"] == "flood_rescue"
    assert a["priority"] == "Critical"
