"""AI RESQ backend: FastAPI + SQLite. Run: uvicorn main:app --reload --port 8000

Rules enforced here (not just in the UI):
- A team can hold at most ONE active assignment (assigned / accepted / in_progress).
  Enforced by a lock, an explicit check, and a partial UNIQUE index in SQLite.
- Team availability is derived from active assignments, never stored, so it can't drift.
- Status can only move forward: new -> assigned -> accepted -> in_progress -> resolved.
  The only way back is an explicit team "decline" (assigned -> new) or coordinator reassignment before acceptance.
- Every report needs a location: map pin (lat+lng) or a meaningful landmark/address.
"""
import json
import math
import os
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, model_validator

from ai import TEAM_LABELS, analyze

DB = Path(os.getenv("RESQ_DB", Path(__file__).with_name("resq.db")))
app = FastAPI(title="AI RESQ (simulation)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
WRITE_LOCK = threading.Lock()

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
ACTIVE = ("assigned", "accepted", "in_progress")
TEAM_TRANSITIONS = {"assigned": "accepted", "accepted": "in_progress", "in_progress": "resolved"}
REPORT_TYPES = {"flood", "fire", "medical", "accident", "road", "supplies", "other"}
DUP_RADIUS_KM, DUP_WINDOW_MIN = 0.5, 60

TEAM_SELECT = f"""SELECT t.id, t.name, t.type, t.lat, t.lng, t.on_duty, (SELECT r.id FROM reports r WHERE r.team_id=t.id AND r.status IN {ACTIVE}) AS active_report_id,
  CASE WHEN t.on_duty=0 THEN 'off_duty'
       WHEN EXISTS(SELECT 1 FROM reports r WHERE r.team_id=t.id AND r.status IN {ACTIVE}) THEN 'busy'
       ELSE 'available' END AS status
  FROM teams t"""


def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def now():
    return datetime.now(timezone.utc).isoformat()


def _columns(con, table):
    return {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate(con):
    """Bring an older resq.db up to the current schema in place. Additive only: never drops or deletes rows.
    Older schemas: v1 (first scaffold) had teams.status stored and no teams.on_duty / reports.duplicate_of."""
    if "on_duty" not in _columns(con, "teams"):
        con.execute("ALTER TABLE teams ADD COLUMN on_duty INTEGER NOT NULL DEFAULT 1")
    if "duplicate_of" not in _columns(con, "reports"):
        con.execute("ALTER TABLE reports ADD COLUMN duplicate_of INTEGER")
    # v1 stored teams.status; it's kept for compatibility but no longer read (availability is derived).
    try:
        con.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_team ON reports(team_id) WHERE status IN {ACTIVE}")
    except sqlite3.IntegrityError:
        # Old data already double-books a team. Keep every record; the lock + explicit check in assign()
        # still block new double-bookings. The coordinator can resolve the conflict by hand.
        print("WARNING: existing data has a team with more than one active job; unique index not created.")
    con.commit()


def init(reset=False):
    """Create tables if missing and migrate older databases. reset=True is ONLY used by the explicit
    'Reset demo' action (POST /api/demo/reset); startup never deletes data."""
    con = db()
    if reset:
        con.executescript("DROP TABLE IF EXISTS reports; DROP TABLE IF EXISTS teams;")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL, lat REAL, lng REAL,
        on_duty INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, type TEXT, description TEXT, lat REAL, lng REAL,
        address TEXT, reporter TEXT, phone TEXT, analysis TEXT, priority TEXT, priority_score INTEGER,
        status TEXT NOT NULL DEFAULT 'new', team_id INTEGER, duplicate_of INTEGER,
        created_at TEXT, updated_at TEXT, history TEXT DEFAULT '[]');
    """)
    migrate(con)
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


def get_team(con, tid):
    t = con.execute(TEAM_SELECT + " WHERE t.id=?", (tid,)).fetchone()
    return dict(t) if t else None


def all_teams(con):
    return [dict(t) for t in con.execute(TEAM_SELECT + " ORDER BY t.type, t.name").fetchall()]


def suggest_teams(con, report):
    """Matching: right team type first, then available, then nearest. Busy/off-duty teams are listed but not selectable."""
    need = json.loads(report["analysis"])["recommended_team_type"]
    out = []
    for t in all_teams(con):
        d = km(report["lat"], report["lng"], t["lat"], t["lng"])
        assignable = t["status"] == "available" or t["id"] == report["team_id"]
        score = (50 if t["type"] == need else 0) + (40 if assignable else -100) - (d or 0)
        out.append({**t, "distance_km": d, "type_match": t["type"] == need, "assignable": assignable, "match_score": round(score, 1)})
    return sorted(out, key=lambda x: -x["match_score"])


def mask_phone(p):
    """Privacy: show only the last 2 digits outside the coordinator's detail view."""
    digits = re.sub(r"\D", "", p or "")
    return "" if not digits else ("•" * max(len(digits) - 2, 0)) + digits[-2:]


def row_out(con, r, reveal=False):
    d = dict(r)
    if not reveal:
        d["phone"] = mask_phone(d.get("phone"))
    d["analysis"] = json.loads(r["analysis"])
    d["history"] = json.loads(r["history"])
    d["recommended_team_label"] = TEAM_LABELS.get(d["analysis"]["recommended_team_type"], "General")
    sec = d["analysis"].get("secondary_team_type")
    d["secondary_team_label"] = TEAM_LABELS.get(sec) if sec else None
    d["team"] = get_team(con, r["team_id"]) if r["team_id"] else None
    return d


def fetch(con, rid):
    r = con.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    if not r:
        raise HTTPException(404, f"Report {rid} not found")
    return r


class ReportIn(BaseModel):
    type: str = "other"
    description: str
    lat: float | None = None
    lng: float | None = None
    address: str = ""
    reporter: str = ""
    phone: str = ""

    @field_validator("type")
    @classmethod
    def _type(cls, v):
        if v not in REPORT_TYPES:
            raise ValueError(f"type must be one of {sorted(REPORT_TYPES)}")
        return v

    @field_validator("description")
    @classmethod
    def _desc(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("Please describe what is happening (at least 10 characters).")
        return v.strip()

    @model_validator(mode="after")
    def _location(self):
        if (self.lat is None) != (self.lng is None):
            raise ValueError("Send both lat and lng, or neither.")
        if self.lat is not None and not (-90 <= self.lat <= 90 and -180 <= self.lng <= 180):
            raise ValueError("Coordinates out of range.")
        self.address = self.address.strip()
        meaningful = len(self.address) >= 5 and len(re.findall(r"[A-Za-z]", self.address)) >= 3
        if self.lat is None and not meaningful:
            raise ValueError("Location required: drop a pin / use GPS, or give a landmark or address (5+ characters).")
        return self


class AnalyzeIn(BaseModel):
    description: str
    type: str | None = None


class AssignIn(BaseModel):
    team_id: int


class StatusIn(BaseModel):
    status: str
    team_id: int  # the acting team; required, and it must own the report
    note: str = ""


class DeclineIn(BaseModel):
    team_id: int
    reason: str = ""


class TeamIn(BaseModel):
    name: str
    type: str
    lat: float = CENTER[0]
    lng: float = CENTER[1]

    @field_validator("type")
    @classmethod
    def _type(cls, v):
        if v not in TEAM_LABELS:
            raise ValueError(f"type must be one of {list(TEAM_LABELS)}")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not v.strip():
            raise ValueError("name required")
        return v.strip()


class TeamPatch(BaseModel):
    name: str | None = None
    on_duty: bool | None = None
    lat: float | None = None
    lng: float | None = None


def find_duplicate(con, r: ReportIn, category: str):
    since = (datetime.now(timezone.utc) - timedelta(minutes=DUP_WINDOW_MIN)).isoformat()
    for o in con.execute("SELECT * FROM reports WHERE status!='resolved' AND duplicate_of IS NULL AND created_at>=? ORDER BY id",
                         (since,)).fetchall():
        if json.loads(o["analysis"])["category"] != category:
            continue
        d = km(r.lat, r.lng, o["lat"], o["lng"])
        same_place = (d is not None and d <= DUP_RADIUS_KM) or (r.address and r.address.lower() == (o["address"] or "").lower())
        if same_place:
            return o["id"]
    return None


def create_report(con, r: ReportIn):
    a = analyze(r.description, r.type)
    dup = find_duplicate(con, r, a["category"])
    note = f"AI suggests {a['priority']} ({a['source']})" + (f"; possible duplicate of #{dup}" if dup else "")
    hist = json.dumps([{"at": now(), "status": "new", "note": note}])
    cur = con.execute(
        "INSERT INTO reports(type,description,lat,lng,address,reporter,phone,analysis,priority,priority_score,duplicate_of,"
        "created_at,updated_at,history) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (r.type, r.description, r.lat, r.lng, r.address, r.reporter, r.phone, json.dumps(a), a["priority"],
         a["priority_score"], dup, now(), now(), hist))
    con.commit()
    return cur.lastrowid


def _push(con, rid, status, note, team_id="keep"):
    h = json.loads(fetch(con, rid)["history"]) + [{"at": now(), "status": status, "note": note}]
    if team_id == "keep":
        con.execute("UPDATE reports SET status=?, history=?, updated_at=? WHERE id=?", (status, json.dumps(h), now(), rid))
    else:
        con.execute("UPDATE reports SET status=?, team_id=?, history=?, updated_at=? WHERE id=?",
                    (status, team_id, json.dumps(h), now(), rid))


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/analyze")
def analyze_only(body: AnalyzeIn):
    return analyze(body.description, body.type)


@app.post("/api/reports")
def post_report(body: ReportIn):
    with WRITE_LOCK:
        con = db()
        rid = create_report(con, body)
        out = row_out(con, fetch(con, rid), reveal=True)  # reporter sees their own number
        con.close()
    return out


@app.get("/api/reports")
def list_reports(status: str | None = None, team_id: int | None = None, priority: str | None = None, active: bool = False):
    con = db()
    q, args = "SELECT * FROM reports WHERE 1=1", []
    if status:
        q += " AND status=?"; args.append(status)
    if priority:
        q += " AND priority=?"; args.append(priority)
    if team_id:
        q += " AND team_id=?"; args.append(team_id)
    if active:
        q += f" AND status IN {ACTIVE}"
    q += " ORDER BY (status='resolved'), priority_score DESC, created_at ASC"
    out = [row_out(con, r) for r in con.execute(q, args).fetchall()]
    con.close()
    return out


@app.get("/api/reports/{rid}")
def get_report(rid: int):
    con = db()
    r = fetch(con, rid)
    out = row_out(con, r, reveal=True)  # coordinator detail view: full contact details
    out["suggested_teams"] = suggest_teams(con, r)
    con.close()
    return out


@app.post("/api/reports/{rid}/assign")
def assign(rid: int, body: AssignIn):
    """Human coordinator decision. AI only suggests."""
    with WRITE_LOCK:
        con = db()
        try:
            r = fetch(con, rid)
            t = get_team(con, body.team_id)
            if not t:
                raise HTTPException(404, f"Team {body.team_id} not found")
            if r["status"] not in ("new", "assigned"):
                raise HTTPException(409, f"Report is '{r['status']}'; it can only be (re)assigned before the team accepts.")
            if r["team_id"] == t["id"] and r["status"] == "assigned":
                raise HTTPException(409, f"Already assigned to {t['name']}.")
            if t["status"] == "off_duty":
                raise HTTPException(409, f"{t['name']} is off duty.")
            if t["status"] == "busy":
                raise HTTPException(409, f"{t['name']} is busy with report #{t['active_report_id']}.")
            prev = get_team(con, r["team_id"]) if r["team_id"] else None
            note = f"Assigned to {t['name']} by coordinator" + (f" (reassigned from {prev['name']})" if prev else "")
            _push(con, rid, "assigned", note, team_id=t["id"])
            con.commit()  # previous team becomes available automatically (availability is derived)
        except sqlite3.IntegrityError:
            con.rollback()
            raise HTTPException(409, "Team already has an active assignment.")
        finally:
            con.close()
    return get_report(rid)


@app.post("/api/reports/{rid}/status")
def set_status(rid: int, body: StatusIn):
    """Team moves its job forward one step only: assigned -> accepted -> in_progress -> resolved."""
    if body.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    with WRITE_LOCK:
        con = db()
        try:
            r = fetch(con, rid)
            if r["team_id"] is None or body.team_id != r["team_id"]:
                raise HTTPException(403, "This report is not assigned to your team.")
            allowed = TEAM_TRANSITIONS.get(r["status"])
            if body.status != allowed:
                raise HTTPException(409, f"Invalid transition {r['status']} -> {body.status}"
                                         + (f"; next allowed is '{allowed}'." if allowed else "; report is closed."))
            team = get_team(con, r["team_id"])
            _push(con, rid, body.status, body.note or f"{body.status.replace('_', ' ')} by {team['name'] if team else 'team'}")
            con.commit()
            out = row_out(con, fetch(con, rid))
        finally:
            con.close()
    return out


@app.post("/api/reports/{rid}/decline")
def decline(rid: int, body: DeclineIn):
    """Team declines before accepting: report goes back to the queue and the team is freed."""
    with WRITE_LOCK:
        con = db()
        try:
            r = fetch(con, rid)
            if r["team_id"] != body.team_id:
                raise HTTPException(403, "This report is not assigned to your team.")
            if r["status"] != "assigned":
                raise HTTPException(409, f"Can only decline before accepting (status is '{r['status']}').")
            team = get_team(con, body.team_id)
            _push(con, rid, "new", f"Declined by {team['name']}" + (f": {body.reason}" if body.reason else ""), team_id=None)
            con.commit()
            out = row_out(con, fetch(con, rid))
        finally:
            con.close()
    return out


@app.get("/api/teams")
def teams():
    con = db()
    out = all_teams(con)
    con.close()
    return out


@app.post("/api/teams")
def add_team(body: TeamIn):
    with WRITE_LOCK:
        con = db()
        con.execute("INSERT INTO teams(name,type,lat,lng) VALUES(?,?,?,?)", (body.name, body.type, body.lat, body.lng))
        con.commit()
        con.close()
    return teams()


@app.patch("/api/teams/{tid}")
def patch_team(tid: int, body: TeamPatch):
    with WRITE_LOCK:
        con = db()
        try:
            t = get_team(con, tid)
            if not t:
                raise HTTPException(404, "Team not found")
            if body.on_duty is False and t["status"] == "busy":
                raise HTTPException(409, f"{t['name']} has an active job (#{t['active_report_id']}); finish or reassign it first.")
            for k in ("name", "on_duty", "lat", "lng"):
                v = getattr(body, k)
                if v is not None:
                    con.execute(f"UPDATE teams SET {k}=? WHERE id=?", (int(v) if k == "on_duty" else v, tid))
            con.commit()
            out = get_team(con, tid)
        finally:
            con.close()
    return out


@app.get("/api/stats")
def stats():
    con = db()
    ts = all_teams(con)
    s = {
        "total": con.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
        "open": con.execute("SELECT COUNT(*) FROM reports WHERE status!='resolved'").fetchone()[0],
        "unassigned": con.execute("SELECT COUNT(*) FROM reports WHERE status='new'").fetchone()[0],
        "by_priority": dict(con.execute("SELECT priority, COUNT(*) FROM reports WHERE status!='resolved' GROUP BY priority").fetchall()),
        "by_status": dict(con.execute("SELECT status, COUNT(*) FROM reports GROUP BY status").fetchall()),
        "teams_available": sum(t["status"] == "available" for t in ts),
        "teams_total": len(ts),
    }
    con.close()
    return s


@app.post("/api/demo/reset")
def demo_reset(seed: bool = True):
    """Wipe DB, reseed teams, and (optionally) load the 3 scenarios from the problem statement."""
    with WRITE_LOCK:
        init(reset=True)
        if seed:
            con = db()
            for typ, desc, lat, lng, addr in DEMO_REPORTS:
                create_report(con, ReportIn(type=typ, description=desc, lat=lat, lng=lng, address=addr, reporter="Demo"))
            con.close()
    return stats()


@app.get("/api/meta")
def meta():
    return {"center": CENTER, "team_labels": TEAM_LABELS, "statuses": STATUSES, "report_types": sorted(REPORT_TYPES),
            "demo_reports": [{"type": t, "description": d, "lat": la, "lng": ln, "address": a} for t, d, la, ln, a in DEMO_REPORTS]}
