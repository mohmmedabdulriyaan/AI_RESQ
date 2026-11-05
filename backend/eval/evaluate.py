"""Evaluate the AI analyzer against hand-labelled reports.

Usage (from backend/):
  python eval/evaluate.py          # TEST set: 30 fresh reports, frozen before the P1 fixes, never used for design
  python eval/evaluate.py dev      # DEV set: 27 reports whose errors we have studied and fixed against
  (PowerShell: $env:AI_MODE="rules" first to compare with rules only)

Sets:
  data/training_reports.csv  what the ML model learns from (includes the brief's 3 scenarios)
  eval/dev_reports.csv       development set. It started as our held-out set, but after we analysed its
                             errors and changed rules because of them, it is NO LONGER independent.
  eval/test_reports.csv      test set, written and committed before those changes. Only score it; never tune on it.
                             Its errors have now been looked at once, so any FURTHER fix must come with a new test set.
Labels were written by the team (the same people who wrote the rules), so they are judgement calls, not ground truth,
and the sets are small. The point is to measure consistency and catch regressions, not to claim real-world accuracy.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai import analyze, ai_mode  # noqa: E402

ORDER = ["Low", "Moderate", "High", "Critical"]
SAME_TEAM = {"accident": "medical"}  # accident and medical both route to the medical team


SETS = {"test": Path(__file__).with_name("test_reports.csv"), "dev": Path(__file__).with_name("dev_reports.csv")}


def load(path=SETS["test"]):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run(rows=None, verbose=True, name="test"):
    rows = rows or load(SETS[name])
    pr_ok = cat_ok = within1 = under = 0
    crit_total = crit_found = 0
    confusion = Counter()
    misses = []
    for r in rows:
        a = analyze(r["text"])
        exp_p, got_p = r["priority"], a["priority"]
        exp_c, got_c = SAME_TEAM.get(r["category"], r["category"]), SAME_TEAM.get(a["category"], a["category"])
        confusion[(exp_p, got_p)] += 1
        pr_ok += exp_p == got_p
        cat_ok += exp_c == got_c
        diff = ORDER.index(got_p) - ORDER.index(exp_p)
        within1 += abs(diff) <= 1
        under += diff < 0
        if exp_p == "Critical":
            crit_total += 1
            crit_found += got_p == "Critical"
        if exp_p != got_p or exp_c != got_c:
            misses.append((r["text"], f"{exp_p}/{r['category']}", f"{got_p}/{a['category']}"))
    n = len(rows)
    res = {
        "mode": ai_mode(), "n": n,
        "priority_accuracy": round(pr_ok / n, 3), "category_accuracy": round(cat_ok / n, 3),
        "priority_within_one_level": round(within1 / n, 3), "under_prioritised": under,
        "critical_recall": round(crit_found / crit_total, 3) if crit_total else None,
    }
    if verbose:
        print(f"AI mode: {res['mode']}  |  {name.upper()} set, {n} labelled reports")
        for k in ("priority_accuracy", "category_accuracy", "priority_within_one_level", "critical_recall"):
            print(f"  {k:28s} {res[k]:.0%}")
        print(f"  {'under_prioritised':28s} {under}  (lower than the label: the dangerous kind of error)")
        print("\nConfusion (rows = label, cols = predicted):")
        print("            " + "".join(f"{p:>10s}" for p in ORDER))
        for e in ORDER:
            print(f"  {e:10s}" + "".join(f"{confusion[(e, g)]:>10d}" for g in ORDER))
        if misses:
            print("\nDisagreements (label -> predicted):")
            for t, e, g in misses:
                print(f"  - {t[:70]:70s} {e} -> {g}")
    return res


if __name__ == "__main__":
    run(name=sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in SETS else "test")
