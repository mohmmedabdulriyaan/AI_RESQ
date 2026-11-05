"""Local ML classifier (scikit-learn), free and offline.

Two text classifiers are trained at startup from data/training_reports.csv (the brief's 3 scenarios + 113 hand-written examples, kept
separate from the evaluation set in eval/):
  - category: flood / fire / medical / accident / road_blockage / supplies / other
  - priority: Low / Moderate / High / Critical
Model: TF-IDF features (word 1-2 grams + character 3-5 grams, which cope with typos and word forms)
       -> multinomial Logistic Regression. Training takes well under a second, so there is no model file to manage.

The final analysis is a hybrid (choices made by 5-fold cross-validation on the training set, see eval/crossval.py):
  category: rule keywords if any fire, otherwise the classifier;
  priority: the HIGHER of the classifier's class and the rule score (precautionary), then the rules' safety net:
  explicit life-threat words force Critical, and "everyone is safe" / negated reports are capped Low.
"""
import csv
from functools import lru_cache
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

DATA = Path(__file__).with_name("data") / "training_reports.csv"
PRIORITY_SCORE = {"Low": 20, "Moderate": 47, "High": 70, "Critical": 90}
CATEGORY_TEAM = {"flood": "flood_rescue", "fire": "fire_response", "medical": "medical_response",
                 "accident": "medical_response", "road_blockage": "road_clearance", "supplies": "relief_supply",
                 "other": "general"}
MIN_CAT_CONF = 0.30    # classifier category is used only when rules found no keyword and confidence >= this


def _pipeline():
    feats = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)),
    ])
    return Pipeline([("tfidf", feats), ("clf", LogisticRegression(max_iter=2000, C=10, class_weight="balanced"))])


def load_rows(path=DATA):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def models():
    rows = load_rows()
    texts = [r["text"].lower() for r in rows]
    cat = _pipeline().fit(texts, [r["category"] for r in rows])
    pri = _pipeline().fit(texts, [r["priority"] for r in rows])
    return cat, pri, len(rows)


def _top_words(pipe, text, label, k=3):
    """Words in this report that pushed the model most towards `label` (from the logistic regression weights)."""
    word_vec = pipe.named_steps["tfidf"].transformer_list[0][1]
    clf = pipe.named_steps["clf"]
    x = word_vec.transform([text]).toarray()[0]
    n_word = len(word_vec.get_feature_names_out())
    coef = clf.coef_[list(clf.classes_).index(label)][:n_word]
    contrib = x * coef
    names = word_vec.get_feature_names_out()
    out = []
    for i in np.argsort(contrib)[::-1]:  # display only: skip words like "an", "the" (predictions are unchanged)
        if contrib[i] <= 0 or len(out) == k:
            break
        if not all(w in ENGLISH_STOP_WORDS for w in names[i].split()):
            out.append(names[i])
    return out


def ml_analyze(description: str, reported_type: str | None, rules: dict) -> dict:
    """Combine the classifier with an already-computed rule_analyze() result."""
    from ai import NEXT_STEP, priority_from_score  # local import avoids a cycle

    cat_m, pri_m, n_train = models()
    t = (description or "").lower()
    cat_p = dict(zip(cat_m.classes_, cat_m.predict_proba([t])[0]))
    pri_p = dict(zip(pri_m.classes_, pri_m.predict_proba([t])[0]))
    ml_cat = max(cat_p, key=cat_p.get)
    ml_pri = max(pri_p, key=pri_p.get)

    # Category: rule keywords are precise when they fire; the classifier covers reports with no known keyword.
    # If the reporter says everyone is safe, don't let the classifier re-introduce a negated category ("no fire").
    # Rule keywords win when they fire. With no keyword, the classifier decides; a confident classifier
    # (>= 50%) also overrides the dropdown type, which reporters often leave at its default.
    src = rules.get("category_from", "keywords")
    need = MIN_CAT_CONF if src == "none" else 0.5
    use_ml_cat = src != "keywords" and not rules.get("reported_safe") and cat_p[ml_cat] >= need
    category = ml_cat if use_ml_cat else rules["category"]
    # Priority: precautionary combination, take the HIGHER of the ML class score and the rule score.
    # Chosen by 5-fold cross-validation on the training set (best Critical recall), not tuned on the eval set.
    score = max(PRIORITY_SCORE[ml_pri], rules["priority_score"])
    reasons = [
        f"ML classifier (trained on {n_train} examples): category {ml_cat} {cat_p[ml_cat]:.0%}, "
        f"priority {ml_pri} {pri_p[ml_pri]:.0%}",
    ]
    words = _top_words(pri_m, t, ml_pri)
    if words:
        reasons.append(f"words that drove the ML priority: {', '.join(words)}")
    if category != ml_cat:
        reasons.append(f"category from {'rule keywords' if src == 'keywords' else 'selected type'}: {category}")
    elif src != "keywords":
        reasons.append(f"no rule keyword matched; category from the classifier: {category}")
    reasons.append(f"rule engine score {rules['priority_score']}, ML class score {PRIORITY_SCORE[ml_pri]} -> take the higher: {score}")
    if rules.get("life_threat"):
        if score < 85:
            reasons.append("safety net: explicit life-threat signal -> Critical floor 85")
        score = max(score, 85)
    elif rules.get("reported_safe"):
        if score > 20:
            reasons.append("safety net: reporter says everyone is safe -> capped Low")
        score = min(score, 20)
    score = max(0, min(100, score))
    priority = priority_from_score(score)
    summary = rules["summary"]
    if category != rules["category"]:
        summary = summary.replace(f"{rules['category'].replace('_', ' ').title()} report", f"{category.replace('_', ' ').title()} report", 1)
    team = CATEGORY_TEAM.get(category, "general")
    secondary = rules.get("secondary_team_type")
    if secondary == team:
        secondary = None
    return {
        **rules, "secondary_team_type": secondary,
        "category": category, "priority": priority, "priority_score": score,
        "recommended_team_type": team,
        "summary": summary, "reasons": reasons, "next_step": NEXT_STEP[priority],
        "ml": {"category": ml_cat, "category_confidence": round(cat_p[ml_cat], 3),
               "priority": ml_pri, "priority_confidence": round(pri_p[ml_pri], 3)},
        "source": "ml",
    }
