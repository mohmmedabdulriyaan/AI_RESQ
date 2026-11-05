"""AI RESQ backend: FastAPI + SQLite. Run: uvicorn main:app --reload --port 8000"""
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai import TEAM_LABELS, analyze

DB = Path(__file__).with_name("resq.db")
app = FastAPI(title="AI RESQ (simulation)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Demo area: SR University, Warangal. Change freely.
CENTER = (17.9784, 79.5941)
SEED_TEAMS = [
    ("Flood Rescue Alpha", "flood_rescue", 17.990, 79.580),
    ("Flood Rescue Bravo", "flood_rescue", 17.950, 79.620),
    ("Road Clearance Unit 1", "road_clearance", 17.970, 79.600),
    ("Relief Supply Team 1", "relief_supply", 17.985, 79.560),
    ("Fire Response Unit 1", "fire_response", 18.000, 79.590),
    ("Medical Response 1", "medical_response", 17.965, 79.570),
]
DEMO_REPORTS = [
    ("flood", "Our house is surrounded by floodwater. Four people are trapped, including an elderly person.", 17.992, 79.548, "Near Hanamkonda bus stand"),
    ("road", "A tree has fallen across the road, blocking vehicle movement.", 17.968, 79.612, "Kazipet main road"),
    ("supplies", "We need drinking water and food supplies at our location.", 17.958, 79.585, "Relief camp, ward 12"),
]
STATUSES = ["new", "assigned", "accepted", "in_progress", "resolved"]


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def now():
    return datetime.now(timezone.utc).isoformat()


def init(reset=False):
    con = db()
    if reset:
        con.executescript("DROP TABLE IF EXISTS reports; DROP TABLE IF EXISTS teams;")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, name TEXT, type TEXT, lat REAL, lng REAL,
        status TEXT DEFAULT 'available');
    CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, type TEXT, description TEXT, lat REAL, lng REAL,
        address TEXT, reporter TEXT, phone TEXT, analysis TEXT, priority TEXT, priority_score INTEGER,
        status TEXT DEFAULT 'new', team_id INTEGER, created_at TEXT, updated_at TEXT, history TEXT DEFAULT '[]');
    """)
    if not con.execute("SELECT COUNT(*) FROM teams").fetchone()[0]:
        con.executemany("INSERT INTO teams(name,type,lat,lng) VALUES(?,?,?,?)", SEED_TEAMS)
    con.commit()
    con.close()


init()


def km(a_lat, a_lng, b_lat, b_lng):
    if None in (a_lat, a_lng, b_lat, b_lng):
        return None
    p = math.pi / 180
    h = math.sin((b_lat - a_lat) * p / 2) ** 2 + math.cos(a_lat * p) * math.cos(b_lat * p) * math.sin((b_lng - a_lng) * p / 2) ** 2
    return round(12742 * math.asin(math.sqrt(h)), 2)


def suggest_teams(con, report):
    """Matching: right team type first, then available, then nearest."""
    need = json.loads(report["analysis"])["recommended_team_type"]
    out = []
    for t in con.execute("SELECT * FROM teams").fetchall():
        d = km(report["lat"], report["lng"], t["lat"], t["lng"])
        score = (50 if t["type"] == need else 0) + (40 if t["status"] == "available" else 0) - (d or 0)
        out.append({**dict(t), "distance_km": d, "type_match": t["type"] == need, "match_score": round(score, 1)})
    return sorted(out, key=lambda x: -x["match_score"])


def row_out(con, r):
    d = dict(r)
    d["analysis"] = json.loads(r["analysis"])
    d["history"] = json.loads(r["history"])
    d["recommended_team_label"] = TEAM_LABELS.get(d["analysis"]["recommended_team_type"], "General")
    d["team"] = dict(con.execute("SELECT * FROM teams WHERE id=?", (r["team_id"],)).fetchone()) if r["team_id"] else None
    return d


class ReportIn(BaseModel):
    type: str = "other"
    description: str
    lat: float | None = None
    lng: float | None = None
    address: str = ""
    reporter: str = ""
    phone: str = ""


class AnalyzeIn(BaseModel):
    description: str
    type: str | None = None


class AssignIn(BaseModel):
    team_id: int


class StatusIn(BaseModel):
    status: str
    note: str = ""


class TeamIn(BaseModel):
    name: str
    type: str
    lat: float = CENTER[0]
    lng: float = CENTER[1]


def create_report(con, r: ReportIn):
    a = analyze(r.description, r.type)
    hist = json.dumps([{"at": now(), "status": "new", "note": f"AI: {a['priority']} ({a['source']})"}])
    cur = con.execute(
        "INSERT INTO reports(type,description,lat,lng,address,reporter,phone,analysis,priority,priority_score,created_at,updated_at,history)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (r.type, r.description, r.lat, r.lng, r.address, r.reporter, r.phone, json.dumps(a), a["priority"],
         a["priority_score"], now(), now(), hist))
    con.commit()
    return cur.lastrowid


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/analyze")
def analyze_only(body: AnalyzeIn):
    return analyze(body.description, body.type)


@app.post("/api/reports")
def post_report(body: ReportIn):
    if not body.description.strip():
        raise HTTPException(400, "Description required")
    con = db()
    rid = create_report(con, body)
    out = row_out(con, con.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone())
    con.close()
    return out


@app.get("/api/reports")
def list_reports(status: str | None = None, team_id: int | None = None):
    con = db()
    q, args = "SELECT * FROM reports WHERE 1=1", []
    if status:
        q += " AND status=?"; args.append(status)
    if team_id:
        q += " AND team_id=?"; args.append(team_id)
    q += " ORDER BY (status='resolved'), priority_score DESC, created_at ASC"
    out = [row_out(con, r) for r in con.execute(q, args).fetchall()]
    con.close()
    return out


@app.get("/api/reports/{rid}")
def get_report(rid: int):
    con = db()
    r = con.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    if not r:
        raise HTTPException(404)
    out = row_out(con, r)
    out["suggested_teams"] = suggest_teams(con, r)
    con.close()
    return out


def _push(con, rid, status, note, team_id=None):
    r = con.execute("SELECT history FROM reports WHERE id=?", (rid,)).fetchone()
    h = json.loads(r["history"]) + [{"at": now(), "status": status, "note": note}]
    if team_id is not None:
        con.execute("UPDATE reports SET status=?, team_id=?, history=?, updated_at=? WHERE id=?", (status, team_id, json.dumps(h), now(), rid))
    else:
        con.execute("UPDATE reports SET status=?, history=?, updated_at=? WHERE id=?", (status, json.dumps(h), now(), rid))


@app.post("/api/reports/{rid}/assign")
def assign(rid: int, body: AssignIn):
    """Human coordinator decision. AI only suggests."""
    con = db()
    t = con.execute("SELECT * FROM teams WHERE id=?", (body.team_id,)).fetchone()
    r = con.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    if not t or not r:
        raise HTTPException(404)
    if r["team_id"] and r["team_id"] != t["id"]:
        con.execute("UPDATE teams SET status='available' WHERE id=?", (r["team_id"],))
    _push(con, rid, "assigned", f"Assigned to {t['name']} by coordinator", t["id"])
    con.execute("UPDATE teams SET status='busy' WHERE id=?", (t["id"],))
    con.commit()
    out = get_report(rid)
    con.close()
    return out


@app.post("/api/reports/{rid}/status")
def set_status(rid: int, body: StatusIn):
    if body.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    con = db()
    r = con.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    if not r:
        raise HTTPException(404)
    _push(con, rid, body.status, body.note or f"Status -> {body.status}")
    if body.status == "resolved" and r["team_id"]:
        con.execute("UPDATE teams SET status='available' WHERE id=?", (r["team_id"],))
    con.commit()
    out = row_out(con, con.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone())
    con.close()
    return out


@app.get("/api/teams")
def teams():
    con = db()
    out = [dict(t) for t in con.execute("SELECT * FROM teams ORDER BY type, name").fetchall()]
    con.close()
    return out


@app.post("/api/teams")
def add_team(body: TeamIn):
    con = db()
    con.execute("INSERT INTO teams(name,type,lat,lng) VALUES(?,?,?,?)", (body.name, body.type, body.lat, body.lng))
    con.commit()
    con.close()
    return teams()


@app.get("/api/stats")
def stats():
    con = db()
    s = {
        "total": con.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
        "open": con.execute("SELECT COUNT(*) FROM reports WHERE status!='resolved'").fetchone()[0],
        "by_priority": dict(con.execute("SELECT priority, COUNT(*) FROM reports WHERE status!='resolved' GROUP BY priority").fetchall()),
        "by_status": dict(con.execute("SELECT status, COUNT(*) FROM reports GROUP BY status").fetchall()),
        "teams_available": con.execute("SELECT COUNT(*) FROM teams WHERE status='available'").fetchone()[0],
        "teams_total": con.execute("SELECT COUNT(*) FROM teams").fetchone()[0],
    }
    con.close()
    return s


@app.post("/api/demo/reset")
def demo_reset(seed: bool = True):
    """Wipe DB, reseed teams, and (optionally) load the 3 scenarios from the problem statement."""
    init(reset=True)
    if seed:
        con = db()
        for typ, desc, lat, lng, addr in DEMO_REPORTS:
            create_report(con, ReportIn(type=typ, description=desc, lat=lat, lng=lng, address=addr, reporter="Demo"))
        con.close()
    return stats()


@app.get("/api/meta")
def meta():
    return {"center": CENTER, "team_labels": TEAM_LABELS, "statuses": STATUSES,
            "demo_reports": [{"type": t, "description": d, "lat": la, "lng": ln, "address": a} for t, d, la, ln, a in DEMO_REPORTS]}
