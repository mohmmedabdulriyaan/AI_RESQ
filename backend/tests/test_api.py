PIN = {"lat": 17.98, "lng": 79.59}


def report(c, text="Our house is flooded and two people are trapped on the roof", **kw):
    body = {"type": "flood", "description": text, **PIN, **kw}
    r = c.post("/api/reports", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def team_id(c, name):
    return next(t["id"] for t in c.get("/api/teams").json() if t["name"] == name)


# ---------- location ----------
def test_location_required(client):
    r = client.post("/api/reports", json={"type": "fire", "description": "Fire in the building next door"})
    assert r.status_code == 422


def test_address_must_be_meaningful(client):
    r = client.post("/api/reports", json={"type": "fire", "description": "Fire in the building next door", "address": "12"})
    assert r.status_code == 422
    r = client.post("/api/reports", json={"type": "fire", "description": "Fire in the building next door", "address": "Behind SRU main gate"})
    assert r.status_code == 200


def test_half_coordinates_rejected(client):
    r = client.post("/api/reports", json={"type": "fire", "description": "Fire in the building next door", "lat": 17.9})
    assert r.status_code == 422


# ---------- team allocation ----------
def test_busy_team_cannot_be_double_assigned(client):
    a, b = report(client), report(client, "Tree fallen across the road blocking traffic", lat=17.90, lng=79.50)
    t = team_id(client, "Flood Rescue Alpha")
    assert client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t}).status_code == 200
    r = client.post(f"/api/reports/{b['id']}/assign", json={"team_id": t})
    assert r.status_code == 409 and "busy" in r.json()["detail"]


def test_resolving_frees_team_only_when_no_other_active_job(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    for s in ("accepted", "in_progress", "resolved"):
        assert client.post(f"/api/reports/{a['id']}/status", json={"status": s, "team_id": t}).status_code == 200
    team = next(x for x in client.get("/api/teams").json() if x["id"] == t)
    assert team["status"] == "available"


def test_reassign_before_accept_frees_previous_team(client):
    a = report(client)
    t1, t2 = team_id(client, "Flood Rescue Alpha"), team_id(client, "Flood Rescue Bravo")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t1})
    assert client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t2}).status_code == 200
    status = {x["id"]: x["status"] for x in client.get("/api/teams").json()}
    assert status[t1] == "available" and status[t2] == "busy"


def test_cannot_reassign_after_accept(client):
    a = report(client)
    t1, t2 = team_id(client, "Flood Rescue Alpha"), team_id(client, "Flood Rescue Bravo")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t1})
    client.post(f"/api/reports/{a['id']}/status", json={"status": "accepted", "team_id": t1})
    assert client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t2}).status_code == 409


def test_off_duty_team_not_assignable(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    client.patch(f"/api/teams/{t}", json={"on_duty": False})
    assert client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t}).status_code == 409


def test_busy_team_cannot_go_off_duty(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    assert client.patch(f"/api/teams/{t}", json={"on_duty": False}).status_code == 409


def test_concurrent_assignments_only_one_wins(client):
    from concurrent.futures import ThreadPoolExecutor
    ids = [report(client, f"Flood at house {i}, people trapped", lat=17.9 + i / 10, lng=79.5)["id"] for i in range(5)]
    t = team_id(client, "Flood Rescue Alpha")
    with ThreadPoolExecutor(5) as ex:
        codes = list(ex.map(lambda i: client.post(f"/api/reports/{i}/assign", json={"team_id": t}).status_code, ids))
    assert codes.count(200) == 1 and codes.count(409) == 4


# ---------- status workflow ----------
def test_cannot_go_backwards(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    assert client.post(f"/api/reports/{a['id']}/status", json={"status": "new", "team_id": t}).status_code == 409


def test_cannot_skip_steps(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    # not assigned yet: no team owns it, so no team may move it
    assert client.post(f"/api/reports/{a['id']}/status", json={"status": "accepted", "team_id": t}).status_code == 403
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    assert client.post(f"/api/reports/{a['id']}/status", json={"status": "resolved", "team_id": t}).status_code == 409


def test_resolved_is_final(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    for s in ("accepted", "in_progress", "resolved"):
        assert client.post(f"/api/reports/{a['id']}/status", json={"status": s, "team_id": t}).status_code == 200
    assert client.post(f"/api/reports/{a['id']}/status", json={"status": "in_progress", "team_id": t}).status_code == 409
    assert client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t}).status_code == 409


def test_other_team_cannot_update(client):
    a = report(client)
    t1, t2 = team_id(client, "Flood Rescue Alpha"), team_id(client, "Flood Rescue Bravo")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t1})
    assert client.post(f"/api/reports/{a['id']}/status", json={"status": "accepted", "team_id": t2}).status_code == 403


def test_decline_returns_to_queue(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    r = client.post(f"/api/reports/{a['id']}/decline", json={"team_id": t, "reason": "boat unavailable"})
    assert r.status_code == 200 and r.json()["status"] == "new" and r.json()["team_id"] is None


# ---------- duplicates, filters, demo ----------
def test_duplicate_flagged(client):
    a = report(client)
    b = report(client, "Water rising fast, family trapped upstairs", lat=17.981, lng=79.591)
    assert b["duplicate_of"] == a["id"]
    c = report(client, "Flood far away, people trapped", lat=18.2, lng=79.9)
    assert c["duplicate_of"] is None


def test_priority_filter_and_demo_seed(client):
    client.post("/api/demo/reset?seed=true")
    rs = client.get("/api/reports").json()
    assert [r["priority"] for r in rs] == ["Critical", "High", "Moderate"]
    assert len(client.get("/api/reports?priority=Critical").json()) == 1


# ---------- team_id required on every status transition (regression) ----------
def test_status_requires_team_id(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    r = client.post(f"/api/reports/{a['id']}/status", json={"status": "accepted"})
    assert r.status_code == 422
    assert client.get(f"/api/reports/{a['id']}").json()["status"] == "assigned"  # unchanged


def test_status_null_team_id_rejected(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    assert client.post(f"/api/reports/{a['id']}/status", json={"status": "accepted", "team_id": None}).status_code == 422


def test_every_transition_checks_ownership(client):
    a = report(client)
    t1, t2 = team_id(client, "Flood Rescue Alpha"), team_id(client, "Flood Rescue Bravo")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t1})
    for s in ("accepted", "in_progress", "resolved"):
        assert client.post(f"/api/reports/{a['id']}/status", json={"status": s, "team_id": t2}).status_code == 403
        assert client.post(f"/api/reports/{a['id']}/status", json={"status": s}).status_code == 422
        assert client.post(f"/api/reports/{a['id']}/status", json={"status": s, "team_id": t1}).status_code == 200
    assert client.get(f"/api/reports/{a['id']}").json()["status"] == "resolved"


def test_unknown_team_cannot_update(client):
    a = report(client)
    t = team_id(client, "Flood Rescue Alpha")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    assert client.post(f"/api/reports/{a['id']}/status", json={"status": "accepted", "team_id": 9999}).status_code == 403


# ---------- privacy ----------
def test_phone_masked_in_lists_full_in_coordinator_detail(client):
    a = report(client, phone="+91 98765 43210")
    assert a["phone"] == "+91 98765 43210" or a["phone"].endswith("10")
    listed = client.get("/api/reports").json()[0]["phone"]
    assert "98765" not in listed and listed.endswith("10")
    assert "98765" in client.get(f"/api/reports/{a['id']}").json()["phone"]
    t = team_id(client, "Flood Rescue Alpha")
    client.post(f"/api/reports/{a['id']}/assign", json={"team_id": t})
    team_view = client.get(f"/api/reports?team_id={t}").json()[0]["phone"]
    assert "98765" not in team_view
    upd = client.post(f"/api/reports/{a['id']}/status", json={"status": "accepted", "team_id": t}).json()
    assert "98765" not in upd["phone"]
