"""AI analyzer: LLM first (if a key is set), rule-based fallback always available.

Output schema (both paths return exactly this):
{
  category, priority, priority_score (0-100), people_affected (int|None),
  vulnerable (list[str]), hazards (list[str]), recommended_team_type,
  summary, next_step, source ("llm"|"rules")
}
"""
import json
import os
import re

import httpx

CATEGORIES = {
    "flood": {"team": "flood_rescue", "base": 55, "words": ["flood", "floodwater", "water level", "submerged", "drowning", "inundat", "rising water"]},
    "fire": {"team": "fire_response", "base": 60, "words": ["fire", "smoke", "burning", "flames", "blaze", "explosion", "gas leak"]},
    "medical": {"team": "medical_response", "base": 55, "words": ["injured", "bleeding", "unconscious", "heart attack", "not breathing", "ambulance", "hurt", "fracture", "pregnant"]},
    "accident": {"team": "medical_response", "base": 55, "words": ["accident", "crash", "collision", "overturned", "hit by"]},
    "road_blockage": {"team": "road_clearance", "base": 62, "words": ["tree", "fallen", "road blocked", "blocking", "landslide", "debris", "blocked road", "across the road"]},
    "supplies": {"team": "relief_supply", "base": 40, "words": ["food", "drinking water", "supplies", "shortage", "hungry", "shelter", "blanket", "medicine supply"]},
}

LIFE_THREAT = ["trapped", "stuck", "drowning", "unconscious", "not breathing", "bleeding", "collapsed", "spreading", "can't get out", "cannot get out", "roof", "inside", "help us"]
VULNERABLE = {"elderly": ["elderly", "old man", "old woman", "senior", "grandmother", "grandfather", "aged"],
              "child": ["child", "children", "kid", "baby", "infant", "toddler"],
              "pregnant": ["pregnant"], "disabled": ["disabled", "wheelchair", "bedridden"]}
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "twelve": 12, "twenty": 20, "dozen": 12, "several": 5, "many": 10}
TYPE_ALIASES = {"flood": "flood", "fire": "fire", "medical": "medical", "accident": "accident",
                "road": "road_blockage", "road_blockage": "road_blockage", "supplies": "supplies", "food": "supplies"}

TEAM_LABELS = {"flood_rescue": "Flood Rescue Team", "fire_response": "Fire Response Team", "medical_response": "Medical Response Team",
               "road_clearance": "Road Clearance Team", "relief_supply": "Relief Supply Team", "general": "General Response Team"}


def priority_from_score(score: int) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 35:
        return "Moderate"
    return "Low"


NEXT_STEP = {
    "Critical": "Immediate human review and rescue-team alert (simulation).",
    "High": "Review soon and assign the recommended team.",
    "Moderate": "Queue for assignment; confirm needs with reporter.",
    "Low": "Log and monitor; assign when resources free up.",
}


def _people(text: str):
    m = re.search(r"(\d+)\s*(?:\w+\s){0,2}(?:people|persons|members|of us|residents|families|trapped|injured|kids|children)", text)
    if m:
        return int(m.group(1))
    for w, n in NUM_WORDS.items():
        if re.search(rf"\b{w}\b\s*(?:\w+\s){{0,2}}(?:people|persons|members|of us|residents|families|trapped|injured|kids|children)", text):
            return n
    return None


def rule_analyze(description: str, reported_type: str | None = None) -> dict:
    t = (description or "").lower()
    has = lambda w: re.search(rf"\b{re.escape(w)}", t) is not None
    hits = {c: sum(has(w) for w in d["words"]) for c, d in CATEGORIES.items()}
    category = max(hits, key=hits.get) if max(hits.values()) > 0 else None
    if category is None:
        category = TYPE_ALIASES.get((reported_type or "").lower(), "other")
    base = CATEGORIES.get(category, {"base": 30})["base"]

    hazards = [w for w in LIFE_THREAT if has(w)]
    vulnerable = [k for k, ws in VULNERABLE.items() if any(has(w) for w in ws)]
    people = _people(t)

    score = base + (20 + 5 * (len(hazards) - 1) if hazards else 0) + 8 * len(vulnerable)
    if people:
        score += min(people, 10) * 2
    score = max(0, min(100, score))
    priority = priority_from_score(score)
    team = CATEGORIES.get(category, {"team": "general"})["team"]

    parts = [f"{category.replace('_', ' ').title()} report"]
    if people:
        parts.append(f"{people} people affected")
    if vulnerable:
        parts.append("vulnerable: " + ", ".join(vulnerable))
    if hazards:
        parts.append("risk signals: " + ", ".join(hazards))
    return {
        "category": category, "priority": priority, "priority_score": score,
        "people_affected": people, "vulnerable": vulnerable, "hazards": hazards,
        "recommended_team_type": team, "summary": "; ".join(parts) + ".",
        "next_step": NEXT_STEP[priority], "source": "rules",
    }


LLM_PROMPT = """You are a triage assistant inside a SIMULATED emergency coordination prototype (not real dispatch).
Analyze the report and reply with ONLY a JSON object, no prose, with keys:
category: one of flood|fire|medical|accident|road_blockage|supplies|other
priority_score: integer 0-100 (80+ Critical life threat, 60-79 High, 35-59 Moderate, <35 Low)
people_affected: integer or null
vulnerable: array of strings (e.g. elderly, child, pregnant, disabled)
hazards: array of short strings
recommended_team_type: one of flood_rescue|fire_response|medical_response|road_clearance|relief_supply|general
summary: one sentence a coordinator can read in 3 seconds

Reported type: {rtype}
Report: {desc}"""


def _llm(description: str, reported_type: str | None):
    prompt = LLM_PROMPT.format(rtype=reported_type or "unspecified", desc=description)
    if os.getenv("ANTHROPIC_API_KEY"):
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=15, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"), "max_tokens": 400,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        text = r.json()["content"][0]["text"]
    elif os.getenv("OPENAI_API_KEY"):
        r = httpx.post("https://api.openai.com/v1/chat/completions", timeout=15, headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "response_format": {"type": "json_object"},
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
    else:
        return None
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    score = max(0, min(100, int(data["priority_score"])))
    priority = priority_from_score(score)
    team = data.get("recommended_team_type") if data.get("recommended_team_type") in TEAM_LABELS else "general"
    return {
        "category": data.get("category", "other"), "priority": priority, "priority_score": score,
        "people_affected": data.get("people_affected"), "vulnerable": data.get("vulnerable") or [],
        "hazards": data.get("hazards") or [], "recommended_team_type": team,
        "summary": data.get("summary", ""), "next_step": NEXT_STEP[priority], "source": "llm",
    }


def analyze(description: str, reported_type: str | None = None) -> dict:
    if os.getenv("AI_MODE", "auto") != "rules":
        try:
            out = _llm(description, reported_type)
            if out:
                return out
        except Exception as e:  # any LLM failure -> deterministic fallback, demo never breaks
            print("LLM failed, using rules:", e)
    return rule_analyze(description, reported_type)
