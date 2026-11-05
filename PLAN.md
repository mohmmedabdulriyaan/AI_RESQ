# AI RESQ — 6-hour plan

## Is ChatGPT's breakdown right?
Mostly yes. Users, six features, three demo scenarios, final deliverables and the simulation-only rule all match the brief. Things it missed or underplayed:

1. **"People struggle to communicate their exact location"** is half of the problem statement. A plain address box doesn't answer it. The scaffold has a "Use my location" GPS button, tap-the-map pin, and a landmark field.
2. **"Multiple requests simultaneously"** means the dashboard must be a *ranked queue*, not a list. The brief says "priority scoring to rank requests", so there's a 0-100 score and the queue sorts by it.
3. **Generative summarization** is listed as an AI technique. Each report gets a one-line summary for the coordinator.
4. **"Live" dashboard** should visibly update without refresh (polling every 3s; the scaffold does this).
5. **The safety line "Never delay contacting emergency services"** should be visible in the UI, not just in the pitch. There's a banner on every page.
6. Small nit: the doc doesn't say the response team should "update status" beyond accept, but a resolve step makes the loop close (team becomes available again), which demos well.
7. "AI decides vs human decides": correct, keep it. The UI labels assignment as the coordinator's decision and shows the AI suggestion starred.

## What's already done (scaffold)
The scaffold implements the full workflow (report → AI → queue/map → assign → team accept → resolve). Local analysis ranks the flood, blocked road, and relief supplies scenarios Critical, High, and Moderate respectively.
So use the 6 hours on **making it impressive and robust**, not on plumbing.

## Update after review (done)
Fixed: team double-booking, forward-only statuses, negation + life-threat rules with "why this priority", required location + GPS recenter,
dashboard filters, team management (add / on-off duty), duplicate flag, visible errors, decline, 33 pytest tests.
So in the table below, the hour 1-3 items for filters, team management, duplicates and explainability are already done.
The merged version defaults to local scikit-learn plus rules (`AI_MODE=ml`). The suite now covers workflow rules, migration, privacy, ML, and evaluation in 78 automated tests. Role tabs share a simulation API, and map tiles need internet.

## Split
- **Person 1 (Claude Code) — Backend + AI:** `backend/`. Owns `ai.py`, matching, API.
- **Person 2 (Codex) — Frontend + demo:** `frontend/`. Owns UI, map, polish, demo script.
- The API contract is in README. Coordinate overlapping edits locally and wait for approval before pushing the merge.

## Hour by hour (inspections every hour)
| Hour | Person 1 (backend/AI) | Person 2 (frontend/demo) | Show at inspection |
|---|---|---|---|
| 0-1 | Get both machines running. Confirm local ML mode on the three sample scenarios. | Run frontend, walk all 3 tabs, note bugs. Pick colours/logo. | Working app, 3 scenarios analyzed |
| 1-2 | Review the local classifier and rules on additional development examples (fire, accident, and mixed-language text if time). | Polish report form (mobile layout, success state), dashboard filters by priority/status. | **Core MVP:** submit → AI → admin sees it with priority + resource |
| 2-3 | Team management (add team form endpoint already exists; add team location editing). Duplicate-report detection (same area + category in 30 min → flag). | Team management UI; map legend; click marker → open details. | Full workflow incl. assign + accept |
| 3-4 | "Explain why" field: which words drove the priority (great for judges). Small eval script: accuracy on your test set. | Sound/flash for new Critical report on dashboard; empty/loading/error states. | AI explainability + live alerts |
| 4-5 | Freeze features. Fix bugs, seed realistic data (8-10 reports). | Final polish, screenshots, README screenshots. | Polished demo |
| 5-6 | Rehearse the demo twice with the README walkthrough. Record a backup screen video in case the map tiles fail. | Same. Slides only if required. | Final demo |

## Risks
- **Wi-Fi down at judging:** The local analyzer runs offline. Map tiles need internet, so keep the backup video ready.
- **Merge conflicts:** split by folder as above.
- **Scope creep:** no login/auth, no Firebase. Role tabs are enough for a simulation.
