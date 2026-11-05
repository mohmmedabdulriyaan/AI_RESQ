# AI RESQ: demo-day checklist

Tick each box as you go. Expected results were checked against the current code (default AI mode, local ML + rules).

## A. 10 minutes before judges arrive

- [ ] Follow the [README setup](README.md#run-it-2-terminals), including the Python dependencies.
- [ ] In the backend terminal set `AI_MODE=ml` and point `RESQ_DB` to a disposable demo database.
- [ ] Start Uvicorn from `backend/` and Vite from `frontend/`. Open http://localhost:5173.
- [ ] Check that the dashboard and map load. Street tiles need internet access.
- [ ] Keep a third terminal in `backend/` for the evaluation commands.
- [ ] Decide who presents what using section F.

## B. Opening (30 seconds)
> "In floods and accidents, people can't say where they are or what they need, and coordinators get many requests at once.
> AI RESQ lets anyone report with GPS, AI ranks urgency and suggests the right team, and a human coordinator decides.
> It's a simulation and decision-support prototype, not real dispatch. In a real emergency, call 112."

Point at the **simulation notice** at the top that says this.

## C. Main demo (about 3 minutes)

### 1. The brief's 3 scenarios
- [ ] Submit the three named **Sample scenarios** on the disposable database. The priority queue shows them in this order:

| Report | Expected priority | Expected team |
|---|---|---|
| Flood, 4 trapped incl. elderly | **Critical** | Flood rescue |
| Tree fallen across road | **High** | Road clearance |
| Need drinking water and food | **Moderate** | Relief supply |

- [ ] Point out the coloured pins on the map, and the stats row (open, Critical, teams available)

### 2. Live report: the AI in action
- [ ] **Report emergency** tab → type: *Bike accident near the college gate, man bleeding and unconscious, two others injured*
- [ ] Type: **Road accident** → click **Use my location** or enter a landmark → **Submit report**
- [ ] Expected: **Critical, Medical Response Team**, people affected shown
- [ ] Click **Why this priority?** and read it out: the ML model's confidence, the words that drove it, the rule score, and the life-threat safety net ("unconscious")
- [ ] Say: "AI suggestion only. A human reviews every request."

### 3. Coordinator assigns
- [ ] **Coordinator dashboard** → find the new report in the priority queue
- [ ] Click it → the team dropdown shows **Type match** and distance in km
- [ ] Point out that **busy teams are greyed out** (can't be double-booked)
- [ ] Click **Assign team** → green "Assigned to …" message, and the timeline updates

### 4. Response team completes it
- [ ] **Response team console** → pick that team → **Accept assignment** → **Start work** → **Mark resolved**
- [ ] Back to the dashboard: status **resolved**, the team shows **available** again, and the timeline has every step with times

## D. Robustness tests (do 3 or 4 of these; judges love them)

| Test | How | Expected |
|---|---|---|
| **No location** | Report tab, type any description, don't pin, clear the landmark, Submit | The landmark field shows the location error |
| **Too short** | Description `help`, Submit | Refused (minimum 10 characters) |
| **Negation** | Type **Other**, text *There is no fire here, everyone is safe.* | **Low**. "Why" says the negated word was ignored and the report capped Low |
| **Vulnerable people** | *House on fire, smoke everywhere, two children inside* | **Critical**, Fire Response Team, vulnerable: child |
| **Two needs at once** | *A person is unconscious and bleeding near a building fire.* | **Critical, Medical Response Team**, with **Fire Response Team** as the secondary resource |
| **Flood stranding** | *Family of five stuck on the roof, water still rising, baby with us* | **Critical, Flood rescue**, 5 people |
| **No keywords (pure ML)** | Type **Other**, text *The lift is stuck between floors with four people inside* | **High**. "Why" says the category came from the classifier |
| **Double-booking** | Assign a team to report A, then open report B | That team is greyed out as busy and can't be chosen |
| **Duplicate** | Submit a second flood report pinned near the first | Yellow "possible duplicate of #…" flag, nothing merged |
| **Filters** | Dashboard → choose **Critical** in the priority filter | Only Critical reports are listed |
| **Team management** | Teams panel → **Set off duty** on a free team → **Add response team** | The off-duty team can't be assigned; the new team appears |
| **Privacy** | Submit a test phone number. Compare the report list API and the coordinator's incident detail | The API list masks all but the last two digits. The detail view shows the full number |
| **Backend down** | Ctrl+C in terminal 1, wait 3 s on the dashboard | The queue shows **Updates paused** and a connection error, no crash. Restart uvicorn and it recovers |

## E. Show the AI evaluation (1 minute, terminal 3)
```
python eval/evaluate.py
```
This is the **independent test set**: 30 reports written and committed before our last fixes, never used to design anything. Expected:
- Priority accuracy **67%**, category **90%**, within one level **87%**, Critical recall **75%**, under-rated **5**

Compare with rules only (PowerShell):
```
$env:AI_MODE="rules"; python eval/evaluate.py; Remove-Item Env:AI_MODE
```
- Rules only: priority **40%**, category **53%**, Critical recall **17%**, under-rated **16**

Say: "On wording it has never seen, the ML model is what makes it work: Critical recall goes from 17% to 75%. It's still wrong on one in three priorities, which is exactly why a human coordinator reviews every report and team suggestion. We kept this test set separate on purpose: our first held-out set stopped being independent once we fixed errors against it, so we renamed it the dev set (`python eval/evaluate.py dev`) and wrote a fresh one."

Optional: `python eval/crossval.py` shows how we chose the ML + rules combination using training data only.

## F. Rubric checklist: make sure you SAY each of these

| Criterion (points) | What to show or say |
|---|---|
| Problem & impact (10) | Two problems: reporting with location, and prioritising limited teams. Beneficiaries: public, rescue teams, coordinators |
| Prompt engineering (10) | Open **PROMPTS.md**: show the bug-review prompt with evidence and "Fix:" lines, and the constraint prompt (₹0, no deletes, no rebuild) |
| AI implementation (15) | scikit-learn TF-IDF + Logistic Regression **plus** rule NLP; "Why this priority?"; the evaluation numbers |
| UI/UX (10) | Three role tabs, map, colour-coded priorities, error messages, GPS button |
| Working prototype (20) | The full flow in section C, live, end to end |
| Innovation (10) | ML + rule safety net, negation handling, explainable reasons, duplicate detection, double-booking protection |
| Testing (10) | 78 automated tests, the robustness table, the independent test set, honest limits (dev vs test) |
| GitHub (5) | Repo with README, TECH_STACK.md, setup steps, requirements.txt, package.json, tests |
| Responsible AI (5) | Human decides, simulation notice, phone masking, no API keys (₹0, offline), honest about limits |
| Presentation (5) | Each person explains their own part and can answer one question about the other's |

## G. Quick answers if a judge asks
- **"Is this real AI?"** Yes: a trained scikit-learn classifier (TF-IDF + Logistic Regression) plus rule-based NLP, measured on an independent test set.
- **"Why not ChatGPT/an LLM?"** The budget is ₹0. Our model is offline, instant, explainable and measurable. The demo uses `AI_MODE=ml`.
- **"What if the AI is wrong?"** It only suggests. Life-threat words always force Critical, and a human decides.
- **"How do you stop a team going to two places?"** One active job per team, enforced by a lock, a check and a database unique index. Tested with 5 requests at the same moment.
- **"What next?"** SMS/WhatsApp reporting, Telugu/Hindi input, retraining on real data, road-distance routing, login for each role.

More answers are in **TALK.md**, and tool explanations are in **TECH_STACK.md**.

## If something breaks during the demo
| Problem | Fix |
|---|---|
| Dashboard shows **Updates paused** | The backend stopped: in terminal 1, `cd backend`, then `uvicorn main:app --reload --port 8000` |
| "Could not import module main" | You're in the wrong folder: `cd backend` |
| AI card says **Rule engine** on a new report | Check `AI_MODE=ml` and install `requirements.txt` in the backend environment. Restart Uvicorn |
| Need a clean rehearsal | Start the backend with a new disposable `RESQ_DB` path and submit the sample reports |
| Map is grey | No internet for the tiles. Carry on, the rest works offline |
