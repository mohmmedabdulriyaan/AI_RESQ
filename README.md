# AI RESQ — Smart Emergency Response & Resource Allocation (simulation)

Decision-support prototype: the public reports an emergency, AI analyzes severity and resource needs,
a **human coordinator** assigns a team, and the team accepts and updates status. **Not a real dispatch service.**

## Run it (2 terminals)

```bash
# 1. Backend  (Python 3.10+)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000        # API docs: http://localhost:8000/docs

# 2. Frontend (Node 18+)
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

Open the **Coordinator dashboard** tab and click **Reset demo** to load scenarios A, B, C from the problem statement.

### AI mode
| Env var | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Uses Claude (`ANTHROPIC_MODEL`, default `claude-haiku-5-5`) |
| `OPENAI_API_KEY` | Uses OpenAI (`OPENAI_MODEL`, default `gpt-4o-mini`) |
| neither, or `AI_MODE=rules` | Rule-based NLP engine (keywords, people count, vulnerable groups, risk signals) |

Any LLM error falls back to the rule engine automatically, so the demo never breaks. The UI shows which engine produced each analysis.

## How the requirements map to the code

| Requirement (from the brief) | Where |
|---|---|
| Emergency reporting (type, location, description) | `frontend/src/ReportPage.jsx` (GPS button + tap-on-map pin + landmark) |
| AI message analyzer / NLP | `backend/ai.py` (`analyze`, LLM + `rule_analyze`) |
| Urgency classification + priority scoring | `ai.py` → `priority_score` 0-100 → Critical/High/Moderate/Low; queue sorted by score |
| Generative summary | `summary` field (LLM, or templated by rules) |
| Smart resource matching | `main.py` `suggest_teams` (type match + availability + distance) |
| Live dashboard | `AdminPage.jsx` (polls every 3s, stats, priority queue, timeline) |
| Location visualization | Leaflet + OpenStreetMap in `components.jsx` (reports by priority colour, teams in blue) |
| Response team view + accept | `TeamPage.jsx` (assigned → accepted → in_progress → resolved) |
| Human decides | Coordinator picks the team; AI only stars a suggestion |

## API
`POST /api/reports` · `GET /api/reports[?team_id=&status=]` · `GET /api/reports/{id}` (includes ranked `suggested_teams`) ·
`POST /api/reports/{id}/assign {team_id}` · `POST /api/reports/{id}/status {status}` · `GET/POST /api/teams` ·
`GET /api/stats` · `POST /api/analyze` · `POST /api/demo/reset?seed=true` · `GET /api/meta`

## 3-minute demo script
1. Dashboard → **Reset demo**. Queue shows A Critical, B High, C Moderate, pinned on the map.
2. Report tab → type a new one live (e.g. *"Bike accident near the college gate, man bleeding and unconscious, two others injured"*), use location → submit → AI card appears.
3. Dashboard → it jumps into the queue at the right priority. Click it → starred suggested team → **Assign**.
4. Response team tab → pick that team → **Accept** → **Start** → **Resolved**. Dashboard timeline and team availability update live.
5. Close on the limits: simulation only, AI suggests, human decides.
