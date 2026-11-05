# Prompt engineering log

This is a historical record of the project's prompts. Use the [README](README.md) for current setup and workflow.

How we used AI coding tools (Claude Code, Codex, ChatGPT) to build AI RESQ, and how our prompts improved.
Each entry gives the prompt (shortened), what came back, and what we changed in the next prompt.

## 1. Understanding the problem (ChatGPT)
**Prompt:** "Read the whole AI RESQ problem statement and explain exactly what we must build."
**Result:** a good breakdown of users, the 6 features, demo scenarios and deliverables.
**What it missed:** the location problem, ranking requests that arrive at the same time, generative summaries, and showing the safety disclaimer in the UI.
**Lesson:** ask the AI to *check its own breakdown against the source*, not just summarise.

## 2. First build (Claude Code)
**Prompt:** problem statement + ChatGPT breakdown + "we have 6 hours with inspections every hour; verify the breakdown, give an hour-by-hour plan for two people, and scaffold React + Vite, FastAPI, SQLite, Leaflet/OSM, LLM with rule-based fallback, with the 3 demo scenarios seeded."
**Result:** a working end-to-end app (report → AI → dashboard → assign → team accepts), plus a plan and a README.
**Lesson:** giving the stack, the time limit and the acceptance test (the 3 scenarios) up front got a working build first time.

## 3. Review prompt: finding real bugs
We tested the app ourselves and wrote a structured review prompt:
```
Important problems I found
1. Team allocation has a serious bug ... I reproduced this through the API.
   Fix: Prevent busy-team assignments, enforce valid assignment rules ...
2. Priority classification needs improvement
   | Test description | Current result |   (3 failing sentences with scores)
   Fix: Improve the rule engine, add tests for negation and immediate life-threat signals ...
3. Location is not actually required ...
4. Status transitions are insufficiently protected ...
5. Some features are still incomplete or unverified ...
```
**Why it worked:** every point had evidence (a reproduction or a failing input), the expected behaviour, and a "Fix:" line. The AI fixed all 5 and added 33 automated tests.

## 4. Constraint prompt: tightening without breaking things
```
Fix these remaining issues without rebuilding the project:
1. The status API currently allows updates when team_id is omitted. Require team_id ... Add regression tests.
2. The new backend fails against the original SQLite schema ... Add safe, non-destructive schema migration.
   Never automatically delete existing records.
3. Our additional spending budget is strictly ₹0. Make AI_MODE=rules the default ...
4. Add tests for the above changes.
5. Run all backend tests and the frontend build. Fix genuine regressions only.
Preserve the existing functionality and UI. Do not add unrelated features or dependencies.
```
**Refinements compared with prompt 3:**
- Scope limits ("without rebuilding", "do not add unrelated features or dependencies") stopped the AI from rewriting working code.
- Hard constraints written as rules ("never automatically delete", "₹0 budget", "must never execute in rules mode").
- Verification built into the prompt ("run all tests and the build").
**Result:** 22 more tests (55 total). The AI also found an extra bug while testing the migration (an old stored team status hid the live one).

## 5. Rubric-driven prompt
"Go through this document, this is the marking scheme." The AI mapped every criterion to the current app, scored the gaps,
and asked us to choose a free AI upgrade. We picked a **scikit-learn classifier**. The AI then:
- wrote a separate training set and kept the evaluation set held out (a test checks there's no overlap),
- tried several ways to combine ML with the rules, chose one by **cross-validation on training data only**, and reported the
  result honestly: the first version (a blended score) was *worse* than rules on Critical cases, so it was replaced.
**Lesson:** ask for measurements, not claims, and keep the test data out of design decisions.

## 6. Evaluation-integrity prompt
We reproduced two wrong results ("family of five stuck on the roof" → High/General; "pregnant woman in labour, roads flooded" →
Flood rescue) and added: *"Correcting them should not involve training directly on the held-out test examples and then continuing to call
that same set independent."*
**What the AI did:** wrote and committed a fresh test set *before* touching code, renamed the old set to "dev", fixed the errors with
general rules (people stranded in flood water are Critical; a person's medical condition outranks the hazard, with the hazard team as
"also consider"; "family of five" counts people), then scored the fresh set once and reported it honestly, including that most of the
gain was on the dev set.
**Lesson:** say what must stay true about the evaluation, not just what to fix.

## 7. Workflow prompt
"Always work directly in D:\ai-resq\ai-resq instead of sending zip files." Removed the copy-paste step for the rest of the event.

## 8. The prompt inside the product
When `AI_MODE=llm` is enabled, `backend/ai.py` sends this prompt to the model:
- **Role + framing:** "triage assistant inside a SIMULATED emergency coordination prototype (not real dispatch)".
- **Strict output contract:** JSON only, with fixed keys and allowed values for `category` and `recommended_team_type`, so the reply can be parsed and validated.
- **Calibrated scale:** "80+ Critical life threat, 60-79 High, 35-59 Moderate, <35 Low", so scores match the rule engine.
- **Known failure mode called out:** "Handle negation carefully ('no fire' is not a fire)", added after the rule engine failed on negation.
- **Explainability:** asks for `reasons`, shown in the UI as "Why this priority?".
- **Safety net in code:** if the model rates an explicit life-threat signal below Critical, the rules raise it back up.

## What we learned
1. Give evidence (inputs, outputs, reproduction steps), not opinions.
2. State constraints as rules, including what *not* to do.
3. Make the AI verify its own work (tests, build), then check it ourselves.
4. Iterate: each prompt built on what we learned from the last result.
