"""Starting the new backend on a resq.db from the first scaffold must migrate in place, never delete."""
import json
import sqlite3

from conftest import load_app

V1_SCHEMA = """
CREATE TABLE teams(id INTEGER PRIMARY KEY, name TEXT, type TEXT, lat REAL, lng REAL, status TEXT DEFAULT 'available');
CREATE TABLE reports(id INTEGER PRIMARY KEY, type TEXT, description TEXT, lat REAL, lng REAL,
    address TEXT, reporter TEXT, phone TEXT, analysis TEXT, priority TEXT, priority_score INTEGER,
    status TEXT DEFAULT 'new', team_id INTEGER, created_at TEXT, updated_at TEXT, history TEXT DEFAULT '[]');
"""
V1_ANALYSIS = {"category": "flood", "priority": "Critical", "priority_score": 91, "people_affected": 4, "vulnerable": ["elderly"],
               "hazards": ["trapped"], "recommended_team_type": "flood_rescue", "summary": "Flood report.",
               "next_step": "Immediate human review", "source": "rules"}  # v1 had no 'reasons'


def make_v1(path, active_reports=((1, "assigned"),)):
    con = sqlite3.connect(path)
    con.executescript(V1_SCHEMA)
    con.executemany("INSERT INTO teams(id,name,type,lat,lng,status) VALUES(?,?,?,?,?,?)", [
        (1, "Old Flood Team", "flood_rescue", 17.99, 79.58, "busy"),
        (2, "Old Road Team", "road_clearance", 17.97, 79.60, "busy"),  # stale stored status: no active job
    ])
    for i, (team, status) in enumerate(active_reports, start=1):
        con.execute("INSERT INTO reports(id,type,description,lat,lng,address,analysis,priority,priority_score,status,team_id,"
                    "created_at,updated_at,history) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (i, "flood", f"Old report {i}, people trapped", 17.98, 79.59, "Old address", json.dumps(V1_ANALYSIS),
                     "Critical", 91, status, team, "2026-11-05T06:00:00+00:00", "2026-11-05T06:00:00+00:00", "[]"))
    con.execute("INSERT INTO reports(id,type,description,lat,lng,address,analysis,priority,priority_score,status,"
                "created_at,updated_at,history) VALUES(99,'supplies','Need food and water',17.95,79.58,'Camp',?,"
                "'Moderate',40,'new','2026-11-05T06:00:00+00:00','2026-11-05T06:00:00+00:00','[]')",
                (json.dumps({**V1_ANALYSIS, "category": "supplies", "priority": "Moderate"}),))
    con.commit()
    con.close()


def counts(path):
    con = sqlite3.connect(path)
    out = (con.execute("SELECT COUNT(*) FROM teams").fetchone()[0], con.execute("SELECT COUNT(*) FROM reports").fetchone()[0])
    con.close()
    return out


def test_v1_db_migrates_without_losing_records(tmp_path, monkeypatch):
    db = tmp_path / "v1.db"
    make_v1(db)
    before = counts(db)
    _, c = load_app(db, monkeypatch)
    assert counts(db) == before  # nothing deleted, nothing reseeded
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(teams)")}
    assert "on_duty" in cols and "status" in cols  # added, legacy kept
    teams = {t["name"]: t for t in c.get("/api/teams").json()}
    assert teams["Old Flood Team"]["status"] == "busy"        # derived from its active report
    assert teams["Old Road Team"]["status"] == "available"    # stale stored 'busy' is ignored
    assert len(c.get("/api/reports").json()) == 2
    assert c.get("/api/reports/1").json()["duplicate_of"] is None


def test_migrated_db_keeps_working(tmp_path, monkeypatch):
    db = tmp_path / "v1.db"
    make_v1(db)
    _, c = load_app(db, monkeypatch)
    # old assigned report moves forward with ownership enforced
    assert c.post("/api/reports/1/status", json={"status": "accepted", "team_id": 2}).status_code == 403
    assert c.post("/api/reports/1/status", json={"status": "accepted", "team_id": 1}).status_code == 200
    # busy team still can't be double-booked; free team can be assigned
    assert c.post("/api/reports/99/assign", json={"team_id": 1}).status_code == 409
    assert c.post("/api/reports/99/assign", json={"team_id": 2}).status_code == 200
    # new reports, stats and team management work on the migrated schema
    r = c.post("/api/reports", json={"type": "fire", "description": "Fire in the shop next door", "address": "Main bazaar"})
    assert r.status_code == 200
    assert c.patch("/api/teams/2", json={"on_duty": False}).status_code == 409  # busy now
    assert c.get("/api/stats").json()["total"] == 3


def test_migration_is_idempotent(tmp_path, monkeypatch):
    db = tmp_path / "v1.db"
    make_v1(db)
    load_app(db, monkeypatch)
    load_app(db, monkeypatch)  # second start must not fail or change data
    assert counts(db) == (2, 2)


def test_conflicting_legacy_data_is_kept(tmp_path, monkeypatch):
    """v1 bug could leave one team on two active jobs. Startup must not crash or delete either."""
    db = tmp_path / "v1.db"
    make_v1(db, active_reports=((1, "assigned"), (1, "accepted")))
    _, c = load_app(db, monkeypatch)
    assert counts(db) == (2, 3)
    assert {r["id"] for r in c.get("/api/reports?team_id=1").json()} == {1, 2}
    assert c.post("/api/reports/99/assign", json={"team_id": 1}).status_code == 409  # still blocked


def test_fresh_start_seeds_teams_once(tmp_path, monkeypatch):
    db = tmp_path / "new.db"
    load_app(db, monkeypatch)
    load_app(db, monkeypatch)
    assert counts(db) == (6, 0)
