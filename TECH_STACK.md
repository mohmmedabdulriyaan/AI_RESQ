# AI RESQ: tools and technologies

The app and local AI run on a laptop without API keys. OpenStreetMap street tiles need internet access.

```
 Browser (React app)                         Python server (FastAPI)                 Storage
 ┌──────────────────────────┐   JSON over   ┌──────────────────────────────┐       ┌──────────┐
 │ Report / Dashboard / Team│ ── HTTP ────▶ │ API + workflow rules          │ ────▶ │ SQLite   │
 │ Leaflet map (OSM tiles)  │ ◀──────────── │ AI: scikit-learn + rule NLP   │       │ resq.db  │
 └──────────────────────────┘  every 3 s    └──────────────────────────────┘       └──────────┘
   localhost:5173 (Vite)                       localhost:8000 (Uvicorn)
```

## Frontend (folder `frontend/`)

| Tool | What it is | What we use it for | Where |
|---|---|---|---|
| **React 18** | JavaScript library for building UIs from components | The three screens (Report, Coordinator dashboard, Response team) and reusable pieces like the AI analysis card and badges | `src/*.jsx` |
| **Vite 5** | Development server and build tool | Runs the app with instant reload (`npm run dev`), builds the production version (`npm run build`), and forwards `/api` calls to the backend | `vite.config.js` |
| **@vitejs/plugin-react** | Vite plugin | Lets Vite understand JSX (HTML-like syntax inside JavaScript) | `vite.config.js` |
| **Leaflet 1.9** | Open-source map library | Interactive map: tap to drop a pin, coloured circles per priority, team positions | `src/components.jsx` |
| **react-leaflet 4** | React wrapper for Leaflet | Use the map as React components and center it on the selected GPS position | `src/components.jsx` |
| **OpenStreetMap** | Free, community-made world map | The map tiles (the brief suggested it) | map tile URL in `components.jsx` |
| **Browser Geolocation API** | Built into every browser | The **Use my location** button | `src/ReportPage.jsx` |
| **fetch API** | Built into every browser | Sends and receives data from the backend | `src/api.js` |
| **Polling (custom `usePoll` hook)** | Asks the server for updates every 3 s | The "live" dashboard, with no WebSockets to break | `src/api.js` |
| **Plain CSS** | Styling, no framework | Layout, colours, badges, mobile-friendly grid | `src/styles.css` |
| **Hash routing** | `#report`, `#admin`, `#team` in the URL | Switching tabs without an extra routing library | `src/main.jsx` |
| **Node.js + npm** | JavaScript runtime and package manager | Installing the packages above and running Vite | `package.json` |

## Backend (folder `backend/`)

| Tool | What it is | What we use it for | Where |
|---|---|---|---|
| **Python 3** | Programming language | All server and AI logic | `*.py` |
| **FastAPI** | Modern Python web framework | The REST API: create reports, assign teams, update status, stats. Auto-generated API docs at http://localhost:8000/docs | `main.py` |
| **Uvicorn** | Web server for FastAPI | Runs the backend (`uvicorn main:app --reload --port 8000`) | command line |
| **Pydantic** (comes with FastAPI) | Data validation | Rejects bad input: missing location, short descriptions, wrong types, missing team ID | `main.py` (`ReportIn`, `StatusIn`, ...) |
| **SQLite** (built into Python) | File-based database, no server needed | Stores reports and teams in `resq.db`; migrates old databases without deleting data; a unique index blocks double-booking a team | `main.py` |
| **scikit-learn** | Machine learning library | **The AI model.** Two text classifiers (emergency category and priority): TF-IDF features → Logistic Regression. Also 5-fold cross-validation | `ml.py`, `eval/crossval.py` |
| **NumPy** (installed with scikit-learn) | Number arrays | Working with the model's weights to explain which words drove a prediction | `ml.py` |
| **Python `re` (regular expressions)** | Built-in text matching | Rule-based NLP: keywords, negation ("no fire"), people count, vulnerable groups, life-threat words | `ai.py` |
| **Haversine formula** | Maths for distance on a globe | Finds the nearest available team to an emergency | `main.py` (`km`) |
| **threading.Lock** | Built-in | Stops two coordinators assigning the same team at the same moment | `main.py` |
| **httpx** | HTTP client | **Only** for the optional paid LLM mode (`AI_MODE=llm`). Off by default; never used otherwise | `ai.py` |
| **pytest** + FastAPI **TestClient** | Testing framework | 78 automated tests: workflow rules, migration, privacy, AI modes, ML and evaluation | `tests/` |
| **venv** | Python virtual environment | Keeps this project's packages separate from the rest of your system | `backend/.venv` |

## How the AI works, in one paragraph
When a report comes in, two things analyse the text. (1) A **scikit-learn model** trained on 116 labelled example reports turns the text into
TF-IDF numbers (how important each word and letter-group is) and a **Logistic Regression** classifier predicts the category and priority with a
confidence. (2) A **rule engine** finds keywords, handles negation, counts people, spots vulnerable groups (elderly, children) and life-threat words.
We combine them: rule keywords decide the category when they match, and priority is **the higher of the two** (safer). Then life-threat words always
force Critical and "everyone is safe" is capped at Low. The coordinator sees the result and the reasons, and **a human always makes the decision**.

## Data and evaluation files
| File | Purpose |
|---|---|
| `backend/data/training_reports.csv` | 116 labelled reports the model learns from (includes the brief's 3 scenarios) |
| `backend/eval/dev_reports.csv` | 27 development reports (we studied their errors, so they're not independent) |
| `backend/eval/test_reports.csv` | 30 independent test reports, frozen before our last fixes; only scored, never tuned on |
| `backend/eval/evaluate.py` | Accuracy, Critical recall, confusion matrix (`python eval/evaluate.py`) |
| `backend/eval/crossval.py` | How we chose the ML + rules combination (`python eval/crossval.py`) |

## Development tools
| Tool | Use |
|---|---|
| **Claude Code** | Built and fixed most of the code from our structured prompts (see PROMPTS.md) |
| **Codex** | Redesigned the frontend and integrated it with the updated backend |
| **ChatGPT** | First breakdown of the problem statement |
| **VS Code** | Editor and terminals |
| **Git + GitHub** | Version control and the submission repository |

## Why these choices (for judges)
- **React + Vite:** fast to build and reload, and the most common modern web stack.
- **FastAPI:** very little code, automatic validation and free API docs.
- **SQLite instead of Firebase:** no account and no internet needed, and it works for a demo. Firebase was optional in the brief.
- **scikit-learn instead of a paid LLM:** the budget is ₹0, it runs offline, trains locally, and exposes model and rule explanations.
- **Leaflet + OpenStreetMap:** free, no API key (Google Maps would need billing).
