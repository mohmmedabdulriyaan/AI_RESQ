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
Hour 0 is basically finished: full workflow works end to end (report → AI → queue/map → assign → team accept → resolve), rule engine reproduces A=Critical, B=High, C=Moderate, LLM optional with auto fallback.
So use the 6 hours on **making it impressive and robust**, not on plumbing.

## Split
- **Person 1 (Claude Code) — Backend + AI:** `backend/`. Owns `ai.py`, matching, API.
- **Person 2 (Codex) — Frontend + demo:** `frontend/`. Owns UI, map, polish, demo script.
- Contract between you is the API in README. Don't both edit the same file; commit and push every 30-45 min.

## Hour by hour (inspections every hour)
| Hour | Person 1 (backend/AI) | Person 2 (frontend/demo) | Show at inspection |
|---|---|---|---|
| 0-1 | Create GitHub repo, push scaffold, get both machines running. Add API key, test LLM path on A/B/C. | Run frontend, walk all 3 tabs, note bugs. Pick colours/logo. | Working app, repo link, 3 scenarios analyzed |
| 1-2 | Tune LLM prompt + rules on 10-15 extra test sentences (fire, accident, Telugu/Hinglish mixed text if time). | Polish report form (mobile layout, success state), dashboard filters by priority/status. | **Core MVP:** submit → AI → admin sees it with priority + resource |
| 2-3 | Team management (add team form endpoint already exists; add team location editing). Duplicate-report detection (same area + category in 30 min → flag). | Team management UI; map legend; click marker → open details. | Full workflow incl. assign + accept |
| 3-4 | "Explain why" field: which words drove the priority (great for judges). Small eval script: accuracy on your test set. | Sound/flash for new Critical report on dashboard; empty/loading/error states. | AI explainability + live alerts |
| 4-5 | Freeze features. Fix bugs, seed realistic data (8-10 reports). | Final polish, screenshots, README screenshots. | Polished demo |
| 5-6 | Rehearse demo twice with the script in README. Record a backup screen video in case Wi-Fi/LLM fails (set `AI_MODE=rules`). | Same. Slides only if required. | Final demo |

## Risks
- **Wi-Fi/API down at judging:** `AI_MODE=rules` gives identical demo results offline. Map tiles need internet; have the backup video.
- **Merge conflicts:** split by folder as above.
- **Scope creep:** no login/auth, no Firebase. Role tabs are enough for a simulation.
