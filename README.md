# AI RESQ — Smart Emergency Response & Resource Allocation (simulation)

Decision-support prototype: the public reports an emergency, AI analyzes severity and resource needs,
a **human coordinator** assigns a team, and the team accepts and updates status. **Not a real dispatch service.**

## Run it (2 terminals)

```bash
# 1. Backend  (Python 3.10+)
cd backend
python -m pip install -r requirements.txt
AI_MODE=ml python -m uvicorn main:app --reload --port 8000   # API docs: http://localhost:8000/docs

# 2. Frontend (Node 18+)
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

In PowerShell, run `$env:AI_MODE = "ml"` followed by `python -m uvicorn main:app --reload --port 8000` for the backend start.

Use **Sample scenarios** on the reporting page to load any of the three examples into the form. Submit each one to see it in **Coordinator dashboard**.

### AI mode (zero-cost by default)
| `AI_MODE` | Effect |
|---|---|
| unset / `ml` | **Default.** Local scikit-learn classifier with rule-based checks. |
| `rules` | Local keyword, negation, people-count, vulnerability, and life-threat rules. Useful for comparing evaluation results. |

Both modes run offline without API keys. Use `AI_MODE=ml` for the hackathon and keep the upstream paid API mode disabled.
If the classifier cannot load, the backend falls back to rules and the analysis card identifies the engine that produced the report.

### Local classifier

- The category and priority classifiers use TF-IDF over word and character n-grams, followed by logistic regression.
- The models train locally from the 116 labelled reports in `backend/data/training_reports.csv` on first use, then stay in memory.
- Matched rule keywords determine the category. The model can supply a category when the rules find no keyword and confidence meets the threshold.
- Priority takes the higher of the rule score and model class score, then applies the life-threat floor or safe-report cap where appropriate.
- **Why this priority?** shows model confidence, influential words when available, and the rule checks. The analysis card shows a secondary resource when another team type is suggested.

### Upgrading an existing `resq.db`
Startup migrates older databases in place (adds missing columns, keeps every row). Nothing is deleted automatically.
**Reset demo data** deletes reports and team changes. Use it only with permission on a disposable database.
Set `RESQ_DB` to an absolute SQLite path before starting the backend to run a separate demo or test instance.
If older data has a team on two active jobs, startup keeps both jobs and warns. The API blocks new double-bookings.

## How the requirements map to the code

| Requirement (from the brief) | Where |
|---|---|
| Emergency reporting (type, location, description) | `frontend/src/ReportPage.jsx` (GPS button + tap-on-map pin + landmark) |
| AI message analyzer / NLP | `backend/ml.py` (local classifier) and `backend/ai.py` (rules and safety checks) |
| Urgency classification + priority scoring | `ai.py` → `priority_score` 0-100 → Critical/High/Moderate/Low; queue sorted by score |
| Incident summary | `summary` field generated locally from the analysis |
| Smart resource matching | `main.py` `suggest_teams` (type match + availability + distance) |
| Live dashboard | `AdminPage.jsx` (polls every 3s, stats, priority queue, timeline) |
| Location visualization | Leaflet + OpenStreetMap in `components.jsx` (reports by priority colour, teams in blue) |
| Response team view + accept | `TeamPage.jsx` (assigned → accepted → in_progress → resolved) |
| Human decides | Coordinator chooses a team from suggestions labelled with type match and distance |

## Tests
```bash
cd backend
python -m pip install -r requirements.txt pytest
python -m pytest -q
```
The 78 tests cover concurrent assignment, team ownership and status progression, migration, location validation,
duplicate detection, phone masking, local AI modes, the three sample scenarios, and ML evaluation. Database fixtures use temporary files and external AI requests are mocked or blocked.

## AI evaluation

Run from `backend/` with `AI_MODE=ml` for the hybrid model. Set `AI_MODE=rules` in a separate terminal to compare the rules alone.

```bash
python eval/evaluate.py          # Independent test set
python eval/evaluate.py dev      # Development set
python eval/crossval.py          # Five folds on the training set
```

The 116 training examples, 27 development reports, and 30 independent test reports are separate. The team studied the development results when refining the rules. The independent set was reserved for evaluation.

| Mode on the 30-report test set | Priority accuracy | Category accuracy | Within one priority level | Critical recall | Under-prioritised |
|---|---:|---:|---:|---:|---:|
| Rules only | 40% | 53% | 57% | 17% | 16 |
| Local ML + rules | 67% | 90% | 87% | 75% | 5 |

These results come from a small, hand-labelled dataset for the simulation. A human coordinator reviews every priority and team suggestion.

## Privacy

The report list and team updates mask phone numbers to the last two digits. Report creation and the individual report detail endpoint return the full number. The role views share a local simulation API and have no authentication.

## Project notes

- [Technology stack](TECH_STACK.md)
- [Build plan](PLAN.md)
- [Demo checklist](DEMO_CHECKLIST.md) and [talk track](TALK.md)
- [Historical prompt log](PROMPTS.md)

## Workflow rules (enforced by the backend)
- A team holds at most one active job (assigned / accepted / in progress). Enforced by a write lock, an explicit check, and a partial UNIQUE index.
- Team availability is computed from active jobs, never stored, so it can't drift out of sync.
- Status only moves forward: new → assigned → accepted → in_progress → resolved. Invalid moves return 409.
  The coordinator can reassign until the team accepts; the team can decline before accepting (back to the queue).
- Every report needs a map pin/GPS or a landmark/address (5+ characters).
- Similar reports (same category, within 500 m, last 60 min) are flagged as possible duplicates. Nothing is merged automatically.
- Priority labels are heuristic suggestions for a simulation, not validated triage. Every request goes to human review.

## API
`POST /api/reports` · `GET /api/reports[?team_id=&status=&priority=]` · `GET /api/reports/{id}` (includes ranked `suggested_teams`) ·
`POST /api/reports/{id}/assign {team_id}` · `POST /api/reports/{id}/status {status, team_id}` (team_id required; must own the report) · `POST /api/reports/{id}/decline {team_id}` ·
`GET/POST /api/teams` · `PATCH /api/teams/{id} {on_duty}` ·
`GET /api/stats` · `POST /api/analyze` · `POST /api/demo/reset?seed=true` · `GET /api/meta`

## 3-minute demo script
1. Use **Sample scenarios** in **Report emergency** and submit the three examples on a disposable demo database. The queue and map show the flood rescue (Critical), blocked road (High), and relief supplies (Moderate) incidents.
2. Report tab → type a new one live (e.g. *"Bike accident near the college gate, man bleeding and unconscious, two others injured"*), use location → submit → AI card appears.
3. In **Coordinator dashboard**, open the new incident in the priority queue. Choose a suggested team and select **Assign team**.
4. In **Response team console**, select that team, then **Accept assignment**, **Start work**, and **Mark resolved**. The coordinator timeline and team availability update live.
5. Close on the limits: simulation only, AI suggests, human decides.
