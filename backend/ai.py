"""AI analyzer: local ML classifier + rule engine by default (free, offline). External LLM only with explicit AI_MODE=llm + API key.

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
    "flood": {"team": "flood_rescue", "base": 55, "words": ["flood", "floodwater", "water level", "submerged", "drowning", "inundat", "rising water", "water is rising", "water rising", "water still rising", "flooded"]},
    "fire": {"team": "fire_response", "base": 60, "words": ["fire", "smoke", "burning", "flames", "blaze", "explosion", "gas leak"]},
    "medical": {"team": "medical_response", "base": 55, "words": ["injured", "bleeding", "unconscious", "heart attack", "not breathing", "ambulance", "hurt", "fracture", "pregnant", "labour", "labor", "contractions", "giving birth"]},
    "accident": {"team": "medical_response", "base": 55, "words": ["accident", "crash", "collision", "overturned", "hit by"]},
    "road_blockage": {"team": "road_clearance", "base": 62, "words": ["tree", "fallen", "road blocked", "blocking", "landslide", "debris", "blocked road", "across the road"]},
    "supplies": {"team": "relief_supply", "base": 40, "words": ["food", "drinking water", "supplies", "shortage", "hungry", "shelter", "blanket", "medicine supply"]},
}

# Immediate life-threat signals: force Critical (score floor 85).
TIE_ORDER = ["medical", "accident", "fire", "flood", "road_blockage", "supplies"]
# People who can't get away from flood water are in immediate danger even without the word "trapped".
FLOOD_STRANDED = ["stuck", "stranded", "on the roof", "rooftop", "can't get out", "cannot get out", "swept"]
CRITICAL_SIGNALS = ["not breathing", "stopped breathing", "can't breathe", "cannot breathe", "no pulse", "unconscious",
                    "unresponsive", "drowning", "trapped", "cardiac arrest", "heart attack", "severe bleeding",
                    "heavy bleeding", "bleeding heavily", "choking", "buried", "electrocuted", "fainted", "seizure"]
# Serious signals: +10 each (max +25).
SERIOUS_SIGNALS = ["injured", "injuries", "bleeding", "hurt", "stuck", "collapsed", "spreading", "smoke", "burn", "burns",
                   "fracture", "broken", "help needed", "help us", "urgent", "inside", "roof", "rising", "can't get out",
                   "cannot get out"]
SAFE_PHRASES = ["everyone is safe", "everyone safe", "all safe", "all are safe", "we are safe", "no one is hurt", "nobody is hurt",
                "no one hurt", "nobody hurt", "no injuries", "no one injured", "nobody injured", "false alarm", "under control",
                "already resolved"]
NEGATORS = {"no", "not", "never", "without", "nobody", "none", "isn't", "aren't", "wasn't", "weren't", "don't", "doesn't",
            "didn't", "nothing", "neither", "nor"}
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
    "High": "Human review soon, then assign the recommended team.",
    "Moderate": "Human review; queue for assignment and confirm needs with reporter.",
    "Low": "Human review to confirm; log and monitor.",
}


def _people(text: str):
    fam = re.search(r"famil(?:y|ies) of (\d+|\w+)", text)
    if fam:
        v = fam.group(1)
        if v.isdigit():
            return int(v)
        if v in NUM_WORDS:
            return NUM_WORDS[v]
    m = re.search(r"(\d+)\s*(?:\w+\s){0,2}(?:people|person|persons|members|of us|residents|families|trapped|injured|kids|children)", text)
    if m:
        return int(m.group(1))
    for w, n in NUM_WORDS.items():
        if re.search(rf"\b{w}\b\s*(?:\w+\s){{0,2}}(?:people|person|persons|members|of us|residents|families|trapped|injured|kids|children)", text):
            return n
    return None


def _matches(t: str, phrase: str):
    """Yield (start, negated) for each whole-word occurrence of phrase.
    Negated = a negator appears in the 3 words before it, within the same clause."""
    for m in re.finditer(rf"\b{re.escape(phrase)}\b", t):
        clause = re.split(r"[.!?;,]|\bbut\b", t[: m.start()])[-1]
        prev = re.findall(r"[a-z']+", clause)[-3:]
        yield m.start(), any(w in NEGATORS for w in prev)


def rule_analyze(description: str, reported_type: str | None = None) -> dict:
    t = (description or "").lower().replace("\u2019", "'")
    negated: list[str] = []

    def has(phrase):
        found = list(_matches(t, phrase))
        if found and all(n for _, n in found):
            negated.append(phrase)
        return any(not n for _, n in found)

    hits = {c: sum(has(w) for w in d["words"]) for c, d in CATEGORIES.items()}
    # Ties go to the person's own condition first (e.g. labour during a flood is a medical emergency;
    # the flood is the obstacle), then to the hazard. The runner-up becomes a secondary need.
    ranked = sorted((c for c in hits if hits[c] > 0), key=lambda c: (-hits[c], TIE_ORDER.index(c)))
    category = ranked[0] if ranked else None
    secondary = next((c for c in ranked[1:] if CATEGORIES[c]["team"] != CATEGORIES[category]["team"]), None) if ranked else None
    category_from = "keywords"
    if category is None:
        category = TYPE_ALIASES.get((reported_type or "").lower(), "other")
        category_from = "reported_type" if category != "other" else "none"
    base = CATEGORIES.get(category, {"base": 30})["base"]

    critical = [w for w in CRITICAL_SIGNALS if has(w)]
    if hits.get("flood") and not critical:
        stranded = [w for w in FLOOD_STRANDED if has(w)]
        if stranded:
            critical.append(f"stranded in flood water ({stranded[0]})")
    serious = [w for w in SERIOUS_SIGNALS if has(w) and not any(w in c for c in critical)]
    vulnerable = [k for k, ws in VULNERABLE.items() if any(has(w) for w in ws)]
    safe = [p for p in SAFE_PHRASES if has(p)]
    people = _people(t)

    reasons = [f"category '{category}' base {base}"]
    score = base
    if serious:
        bump = min(25, 10 * len(serious)); score += bump
        reasons.append(f"+{bump} serious signals: {', '.join(serious)}")
    if vulnerable:
        score += 8 * len(vulnerable); reasons.append(f"+{8 * len(vulnerable)} vulnerable: {', '.join(vulnerable)}")
    if people:
        score += min(people, 10) * 2; reasons.append(f"+{min(people, 10) * 2} people affected: {people}")
    if critical:
        score = max(score + 15, 85); reasons.append(f"immediate life-threat signal ({', '.join(critical)}) -> Critical floor 85")
    elif safe and not serious:
        score = min(score, 20); reasons.append(f"reporter says situation is safe ({', '.join(safe)}) -> capped Low")
    if negated:
        reasons.append(f"ignored negated words: {', '.join(sorted(set(negated)))}")
    score = max(0, min(100, score))
    priority = priority_from_score(score)
    team = CATEGORIES.get(category, {"team": "general"})["team"]

    parts = [f"{category.replace('_', ' ').title()} report"]
    if people:
        parts.append(f"{people} people affected")
    if vulnerable:
        parts.append("vulnerable: " + ", ".join(vulnerable))
    if critical or serious:
        parts.append("risk signals: " + ", ".join(critical + serious))
    if safe and not critical:
        parts.append("reporter indicates everyone is safe")
    return {
        "category": category, "priority": priority, "priority_score": score,
        "people_affected": people, "vulnerable": vulnerable, "hazards": critical + serious,
        "recommended_team_type": team, "summary": "; ".join(parts) + ".", "reasons": reasons,
        "next_step": NEXT_STEP[priority], "needs_human_review": True, "source": "rules",
        "life_threat": bool(critical), "reported_safe": bool(safe and not serious and not critical),
        "category_from": category_from,
        "secondary_team_type": CATEGORIES[secondary]["team"] if secondary else None,
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
reasons: array of short strings explaining the score
Handle negation carefully ("no fire" is not a fire).

Reported type: {rtype}
Report: {desc}"""


def _llm(description: str, reported_type: str | None):
    if ai_mode() != "llm":  # hard guard: no external request unless explicitly opted in
        raise RuntimeError("External AI disabled (AI_MODE is not 'llm').")
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
        "summary": data.get("summary", ""), "reasons": data.get("reasons") or [], "next_step": NEXT_STEP[priority],
        "needs_human_review": True, "source": "llm",
    }


MODES = ("ml", "rules", "llm")


def ai_mode() -> str:
    """Which analyzer runs. Only 'llm' can make an external (paid) request, and only when set exactly.
    - 'ml'    (default): local scikit-learn classifier + rule safety net. Free, offline.
    - 'rules': rule engine only. Free, offline.
    - 'llm'  : explicit opt-in to an external LLM API (costs money); falls back to ml/rules on any error.
    Unknown values fall back to the local default, so a typo can never cause spending."""
    v = os.getenv("AI_MODE", "ml").strip().lower()
    return v if v in MODES else "ml"


def _local(description: str, reported_type: str | None) -> dict:
    rules = rule_analyze(description, reported_type)
    if ai_mode() == "rules":
        return rules
    try:
        from ml import ml_analyze
        return ml_analyze(description, reported_type, rules)
    except Exception as e:  # scikit-learn missing or model error -> rules, demo never breaks
        print("ML classifier unavailable, using rules:", e)
        return rules


def analyze(description: str, reported_type: str | None = None) -> dict:
    if ai_mode() == "llm":
        try:
            out = _llm(description, reported_type)
            if out:
                # Safety net: never let the LLM rank an explicit life-threat signal below the rule floor.
                rules = rule_analyze(description, reported_type)
                if rules["priority"] == "Critical" and out["priority_score"] < rules["priority_score"]:
                    out["priority_score"] = rules["priority_score"]
                    out["priority"] = priority_from_score(out["priority_score"])
                    out["next_step"] = NEXT_STEP[out["priority"]]
                    out["reasons"] = out["reasons"] + ["raised to Critical by rule safety net: " + ", ".join(rules["hazards"])]
                return out
        except Exception as e:  # any LLM failure -> local fallback
            print("LLM failed, using local analyzer:", e)
    return _local(description, reported_type)
