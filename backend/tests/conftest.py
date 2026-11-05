import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_app(db_path, monkeypatch):
    """(Re)import main against a given SQLite file. Import runs init()/migrate() on that file."""
    import importlib

    monkeypatch.setenv("RESQ_DB", str(db_path))
    import main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    return main, TestClient(main.app)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any external HTTP call during tests is a bug (budget is zero)."""
    import httpx

    def boom(*a, **k):
        raise AssertionError(f"external HTTP request attempted: {a} {k.get('json', '')}")
    monkeypatch.setattr(httpx, "post", boom)
    monkeypatch.setattr(httpx, "get", boom)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    _, c = load_app(tmp_path / "test.db", monkeypatch)
    c.post("/api/demo/reset?seed=false")
    return c
