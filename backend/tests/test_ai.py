"""Rule engine checks. These are heuristic labels for a simulation, not validated triage."""
import pytest

from ai import rule_analyze

CASES = [
    # brief's demo scenarios
    ("Our house is surrounded by floodwater. Four people are trapped, including an elderly person.", "Critical", "flood_rescue"),
    ("A tree has fallen across the road, blocking vehicle movement.", "High", "road_clearance"),
    ("We need drinking water and food supplies at our location.", "Moderate", "relief_supply"),
    # immediate life-threat signals must be Critical
    ("One person is not breathing after a road accident.", "Critical", "medical_response"),
    ("Man unconscious on the pavement near the market", "Critical", "medical_response"),
    ("Child drowning in the canal", "Critical", None),
    ("Severe bleeding from a leg wound after a fall", "Critical", "medical_response"),
    # serious but not explicitly life-threatening
    ("Two people injured in a crash. Help needed.", "High", "medical_response"),
    ("House on fire, smoke everywhere, two children inside", "Critical", "fire_response"),
]


@pytest.mark.parametrize("text,priority,team", CASES)
def test_priority(text, priority, team):
    a = rule_analyze(text)
    assert a["priority"] == priority, (text, a["priority_score"], a["reasons"])
    if team:
        assert a["recommended_team_type"] == team
    assert a["needs_human_review"] is True
    assert a["reasons"]


@pytest.mark.parametrize("text", [
    "There is no fire here, everyone is safe.",
    "False alarm, nobody is hurt.",
    "No flood, no one injured, all safe.",
])
def test_negated_or_safe_reports_are_low(text):
    a = rule_analyze(text)
    assert a["priority"] == "Low", (text, a["reasons"])


def test_negation_only_removes_negated_words():
    a = rule_analyze("Nobody is trapped but water is rising near the school")
    assert "trapped" not in a["hazards"]
    assert a["priority"] != "Critical"


def test_negated_safety_phrase_is_not_safe():
    a = rule_analyze("Not everyone is safe, fire spreading")
    assert a["category"] == "fire"
    assert a["priority"] in ("High", "Critical")


def test_word_boundaries():
    assert rule_analyze("street light not working")["category"] == "other"


def test_people_count():
    assert rule_analyze("Four people are trapped")["people_affected"] == 4
    assert rule_analyze("3 persons injured")["people_affected"] == 3


def test_flood_stranding_is_critical_but_negated_is_not():
    assert rule_analyze("We are stranded on the rooftop, flood water everywhere")["priority"] == "Critical"
    assert rule_analyze("Nobody is stuck, the flood water is going down")["priority"] != "Critical"


def test_family_of_n_counts_people():
    assert rule_analyze("Family of five needs help")["people_affected"] == 5
    assert rule_analyze("families of 3 waiting near the school")["people_affected"] == 3


def test_tie_goes_to_medical_and_runner_up_is_secondary():
    a = rule_analyze("Pregnant woman in labour, roads flooded")
    assert a["category"] == "medical" and a["secondary_team_type"] == "flood_rescue"
    assert rule_analyze("House on fire")["secondary_team_type"] is None
