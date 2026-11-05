"""Evaluation guards. Thresholds are the current measured level (regression checks), not targets.
TEST = fresh set frozen before the P1 fixes (independent). DEV = studied and fixed against (not independent)."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
import evaluate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def texts(path):
    with open(path, encoding="utf-8") as f:
        return {r["text"].strip().lower() for r in csv.DictReader(f)}


def test_sets_are_disjoint():
    train = texts(ROOT / "data" / "training_reports.csv")
    dev, test = texts(evaluate.SETS["dev"]), texts(evaluate.SETS["test"])
    assert not train & dev and not train & test and not dev & test


def test_default_mode_on_independent_test_set(monkeypatch):
    monkeypatch.delenv("AI_MODE", raising=False)
    r = evaluate.run(verbose=False, name="test")
    assert r["mode"] == "ml" and r["n"] == 30
    assert r["priority_accuracy"] >= 0.65
    assert r["category_accuracy"] >= 0.85
    assert r["critical_recall"] >= 0.75


def test_ml_beats_rules_on_test_set(monkeypatch):
    monkeypatch.delenv("AI_MODE", raising=False)
    ml = evaluate.run(verbose=False, name="test")
    monkeypatch.setenv("AI_MODE", "rules")
    rules = evaluate.run(verbose=False, name="test")
    assert ml["critical_recall"] > rules["critical_recall"]
    assert ml["under_prioritised"] < rules["under_prioritised"]


def test_dev_set_regression(monkeypatch):
    monkeypatch.delenv("AI_MODE", raising=False)
    r = evaluate.run(verbose=False, name="dev")
    assert r["priority_accuracy"] >= 0.85 and r["critical_recall"] >= 0.9
