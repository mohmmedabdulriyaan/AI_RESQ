"""5-fold cross-validation on the TRAINING set, used to choose how the classifier and rules are combined.
The dev and test sets (eval/dev_reports.csv, eval/test_reports.csv) are never used for these choices.

Usage (from backend/): python eval/crossval.py
"""
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ml  # noqa: E402
from ai import priority_from_score, rule_analyze  # noqa: E402

S = ml.PRIORITY_SCORE


def safety(rules, score):
    if rules["life_threat"]:
        return max(score, 85)
    if rules["reported_safe"]:
        return min(score, 20)
    return score


STRATEGIES = {
    "rules only": lambda r, arg, exp: r["priority_score"],
    "ML only (argmax)": lambda r, arg, exp: safety(r, S[arg]),
    "blend 60/40 (expected score)": lambda r, arg, exp: safety(r, 0.6 * exp + 0.4 * r["priority_score"]),
    "max(ML, rules)  <- chosen": lambda r, arg, exp: safety(r, max(S[arg], r["priority_score"])),
}


def main():
    rows = ml.load_rows()
    T = np.array([r["text"].lower() for r in rows])
    P = np.array([r["priority"] for r in rows])
    stats = {k: [0, 0, 0] for k in STRATEGIES}  # correct, critical found, under-prioritised
    crit = int((P == "Critical").sum())
    order = list(S)
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(T, P):
        pm = ml._pipeline().fit(T[tr], P[tr])
        for i in te:
            r = rule_analyze(T[i])
            pp = dict(zip(pm.classes_, pm.predict_proba([T[i]])[0]))
            arg, exp = max(pp, key=pp.get), sum(p * S[k] for k, p in pp.items())
            for name, f in STRATEGIES.items():
                got = priority_from_score(round(f(r, arg, exp)))
                stats[name][0] += got == P[i]
                stats[name][1] += P[i] == "Critical" and got == "Critical"
                stats[name][2] += order.index(got) < order.index(P[i])
    print(f"5-fold CV on {len(rows)} training reports (priority)")
    for name, (ok, cf, under) in stats.items():
        print(f"  {name:32s} accuracy {ok / len(rows):.0%}   critical recall {cf / crit:.0%}   under-prioritised {under}")


if __name__ == "__main__":
    main()
