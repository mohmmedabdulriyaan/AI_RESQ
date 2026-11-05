# AI RESQ: talk track (about 5 minutes) and judge Q&A

## 1. Problem (30 s)
In floods, fires and accidents, people can't say exactly where they are or what they need, and coordinators get many requests at once with limited teams.
AI RESQ helps on both sides: easy reporting with location, and a ranked queue with team suggestions for coordinators.
**It's a simulation and decision-support prototype. A human always decides. In a real emergency, call 112.**

## 2. Live demo (3 min)
1. **Report emergency → Sample scenarios.** Submit the three examples on a disposable database. The coordinator queue ranks them: flood Critical, fallen tree High, food/water Moderate, pinned on the map.
2. **Report tab:** type live: *"Bike accident near the college gate, man bleeding and unconscious, two others injured"* → Use my location → Submit. Show the AI card and open **Why this priority?**
3. Try to submit without a location to show it's refused (invalid input handling).
4. **Dashboard:** find the new report in the queue, open it, then choose a team and select **Assign team**. Busy teams are greyed out.
5. **Response team console:** pick that team → **Accept assignment** → **Start work** → **Mark resolved**. The dashboard timeline and team availability update live.
6. Show the evaluation: `python eval/evaluate.py` (accuracy, critical recall, confusion matrix), and compare with rules only.

## 3. How the AI works (1 min)
- **Local machine learning (scikit-learn), free and offline, nothing leaves the laptop:**
  - Two text classifiers (emergency category and priority): **TF-IDF features → Logistic Regression**, trained on 116 labelled reports.
  - Character n-grams cope with typos and word forms ("flooded", "floodwater").
- **Rule-based NLP alongside it:** keyword categories with **negation handling** ("no fire here" is not a fire), people count, vulnerable groups, and life-threat signals.
- **How they combine:** rule keywords decide the category when they match, otherwise the model does. Priority = **the higher of the two** (precautionary), plus a safety net: "not breathing", "unconscious", "trapped" always force Critical, and "everyone is safe" is capped at Low. We chose this combination by cross-validation on the training data only.
- **Explainable:** "Why this priority?" shows model confidence, the words that drove it, and every rule adjustment.
- **Multiple needs:** e.g. labour during a flood → Medical team, with **Flood Rescue Team** shown as the secondary resource.
- **Matching:** the recommended team type first, then available teams, then the nearest by GPS distance (haversine).
- **Demo mode** uses the local classifier and rules (`AI_MODE=ml`) within the ₹0 budget.

## 4. Results and limits (30 s)
- **78 automated tests** and three separate data sets: training, development, and an **independent test set frozen before our last fixes**.
- On the independent test set: rules only → ML + rules: priority accuracy **40% → 67%**, category **53% → 90%**, Critical recall **17% → 75%**, dangerous under-ratings **16 → 5**.
- **Honest limits:** one in three priorities and one in four Critical reports are still wrong on unseen wording. The labels are ours, and the data is small. That's why the AI only suggests, shows its reasons, and a human coordinator decides every time.
- We also caught ourselves: our first "held-out" set stopped being independent once we fixed errors against it, so we renamed it the dev set and wrote a fresh test set before changing anything.

## 5. Who did what
- **Person 1 (backend + AI):** FastAPI, SQLite, ML classifier + rule engine, matching, workflow rules, tests, evaluation.
- **Person 2 (frontend + demo):** React UI, Leaflet map, three role views, UX polish, demo script.
- **Both:** tested the app, wrote the review prompts that found the bugs (see PROMPTS.md).
*(Each of you should be able to explain the other's part at a high level.)*

## Likely judge questions
| Question | Answer |
|---|---|
| Is this really AI? | Yes. A trained ML model (TF-IDF + Logistic Regression, scikit-learn) classifies category and priority, combined with rule-based NLP for negation, entities and life-threat signals. We evaluate it on an independent test set and choose design options by cross-validation on training data. An LLM mode exists but is off because of our ₹0 budget. |
| Why Logistic Regression and not deep learning? | We have 116 examples. A linear model on TF-IDF is the right size: it trains in under a second, runs offline, and its weights explain which words drove each prediction. |
| Why combine ML and rules? | Each misses different things. The model generalises to reports with no known keyword; the rules guarantee safety cases like "not breathing" and handle negation. On the independent test set, adding the model raised Critical recall from 17% to 75%. |
| What if the AI is wrong? | It only suggests. The coordinator sees the reasons and decides. Life-threat words always force Critical, so the most dangerous mistake (under-prioritising) is reduced. We measured it: 5 of 30 under-rated on the independent test set, and we show which ones. |
| How do you stop a team being sent to two places? | The backend allows one active job per team, enforced three ways: a lock, an explicit check, and a unique database index. Tested with 5 requests at the same moment. |
| Privacy? | No API keys in the repo (`.env` is gitignored). Phone numbers are masked except in the coordinator's detail view. Data stays in a local SQLite file. |
| What if Wi-Fi fails? | Rules mode is fully offline. Only the map tiles need internet. |
| Why not Firebase? | It was optional in the brief. SQLite needs no account and no setup, and works offline. |
| What would you add next? | SMS/WhatsApp reporting, Telugu/Hindi input, retraining on real labelled reports, routing by road distance, and login for each role. |
