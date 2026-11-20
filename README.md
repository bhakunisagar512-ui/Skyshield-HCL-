# SkyShield: Aviation Safety and Incident Reporting

SkyShield is an incident reporting system for an airline safety department. Anyone can report an occurrence. A Safety Officer reviews it and writes an analysis. The AI reads that analysis against the company's policy documents and suggests **Must** and **Should** measures, each citing the policy it comes from. The officer marks every measure as applied or not applied, and the admin sees each incident colour-coded by how well it was handled.

```
Report → Review & analyse → AI summary + measures → Mark measures → Close → Admin overview
```

| | |
|---|---|
| **Project** | P06 · SkyShield, Aviation Safety and Incident Reporting System |
| **Domain** | Aerospace and Defence |
| **Repository** | `Skyshield-HCL-` |
| **Team** | Sagar Bhakuni *(add other team members here)* |

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, React Router 6, Bootstrap 5 + Bootstrap Icons, Recharts 3 |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Database | PostgreSQL 16 with the pgvector extension (runs in Docker) |
| Data access | SQLAlchemy 2, Alembic migrations |
| Authentication | JWT (PyJWT), bcrypt password hashing, role-based access |
| AI | Anthropic Claude Haiku (`claude-haiku-5-5`) through a forced tool call; retrieval with pgvector |
| Background work | FastAPI BackgroundTasks |
| Testing | pytest (88 tests), an AI evaluation script (32 cases), an end-to-end smoke test |
| Tools | Git + GitHub, Docker Desktop, VS Code |

## Architecture

```
 Browser ── React app (Reporter / Safety Officer / Admin views)
               │  /api  (Vite dev server forwards to port 8000)
               ▼
 FastAPI ── routers ─► services (workflow, colour rules) ─► AI service (RAG + grounding check)
   │           auth (JWT, roles)   admin + dashboard      background task (AI summary job)
   ▼                                                              │
 PostgreSQL 16 + pgvector (incidents, measures, users,            ▼
 policy chunks and their embeddings)                   Anthropic API (Claude Haiku)
```

## Project structure

```
Skyshield/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app; routers mounted under /api
│   │   ├── config.py            settings read from .env
│   │   ├── database.py          engine, session, consistent_read()
│   │   ├── models.py            SQLAlchemy tables
│   │   ├── schemas.py           Pydantic request/response models and validation
│   │   ├── seed.py              loads database/ into Postgres
│   │   ├── core/                taxonomy (categories, airports…), JWT + bcrypt, role checks
│   │   ├── routers/             auth, incidents, measures, admin, dashboard, policies
│   │   └── services/
│   │       ├── status_rules.py  colour rule, icons, allowed transitions (single source of truth)
│   │       ├── workflow.py      transitions, history, AI background job
│   │       ├── serialize.py     API response shapes + SQL version of the colour rule
│   │       ├── policies.py      policy → chunks → embeddings
│   │       ├── policy_parser.py reads the SOP markdown format
│   │       └── ai/              embeddings.py, llm.py (providers, retries), rag.py (pipeline)
│   ├── alembic/                 database migrations
│   ├── scripts/
│   │   ├── smoke_test.py        end-to-end check against a running server, including the AI
│   │   └── evaluate_ai.py       retrieval and generation metrics on the evaluation set
│   ├── tests/                   88 pytest tests
│   ├── requirements.txt, pytest.ini, alembic.ini
│   └── .env.example             copy to .env (never commit .env)
├── frontend/
│   ├── vite.config.js           dev server on 5173, forwards /api to 8000
│   └── src/
│       ├── api.js, auth.jsx     API client with JWT, login state
│       ├── taxonomy.jsx         dropdown lists from the API, date formatting
│       ├── components/          layout, colour pill, status/priority badges, measure icons
│       └── pages/
│           ├── Login, NewIncident, IncidentList, IncidentDetail, Dashboard
│           ├── officer/Workflow.jsx   review, analysis, AI draft, measures checklist, close
│           └── admin/                 overview, incident view, users, policies
├── database/
│   ├── generate_dataset.py      creates data/*.csv (seeded, reproducible)
│   ├── data/                    users, incidents, measures, ai_summaries, status_history
│   ├── policies/                17 SOP documents the AI reads
│   ├── eval/eval_set.json       32 hand-written incidents with expected answers
│   └── init-test-db.sql         creates the test database when Docker first starts
└── docker-compose.yml           PostgreSQL 16 + pgvector on port 5433
```

## Setup (first time)

You need **Python 3.11+**, **Node.js 18+** and **Docker Desktop**. These commands are for Windows PowerShell; on macOS or Linux, use `source venv/bin/activate` and `cp` instead.

**1. Database** (from the project folder):
```powershell
docker compose up -d db
docker compose exec db pg_isready -U skyshield      # wait for "accepting connections"
```
The database is exposed on port **5433**, so it never clashes with a PostgreSQL already installed on your machine.

**2. Backend:**
```powershell
cd backend
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # only if activation is blocked
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```
Open `backend\.env` and set `JWT_SECRET` to a long random value. You can generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. Then:
```powershell
alembic upgrade head
python -m app.seed --reset        # expect: 17 policies, 16 users, 185 incidents, 1245 measures
python -m pytest -q               # expect: 88 passed
```

**3. Turn on the real AI (optional).** The default is an offline mock, which needs no key. To use Claude, set these in `backend\.env`:
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...        # your key; never commit .env
LLM_MODEL=claude-haiku-5-5          # cheapest model; leave empty for the same default
```

**4. Frontend:**
```powershell
cd ..\frontend
npm install
```

## Running it (every day)

Start **Docker Desktop** first, then open three terminals in the project folder:

| Terminal | Commands | Leave running? |
|---|---|---|
| 1. Database | `docker compose start db` | No, close it after |
| 2. API | `cd backend` · `.\venv\Scripts\Activate.ps1` · `uvicorn app.main:app --reload` | Yes |
| 3. Frontend | `cd frontend` · `npm run dev` | Yes |

Then open:
- **App:** http://localhost:5173. The login page has buttons for the demo accounts.
- **API docs:** http://localhost:8000/docs. Log in with `POST /api/auth/login`, copy the `access_token`, and paste it into **Authorize**.

To check everything at once, including the AI, run this with the API running (in the `backend` folder, venv active): `python -m scripts.smoke_test`

To stop: **Ctrl+C** in terminals 2 and 3, then `docker compose stop db`. Your data is kept. To go back to the clean demo data: `python -m app.seed --reset`.

### Demo logins (password `Password@123`, development only)

| Role | Email |
|---|---|
| Admin | admin@skyshield.example |
| Safety Officer | arjun.mehta@skyshield.example (also kavya.reddy@…, sanjay.bose@…) |
| Reporter | ananya.iyer@skyshield.example (12 reporters in total) |

There is no self sign-up: the admin creates accounts under **Users**.

## What each role can do

- **Reporter:** files a report (with validation), sees "My reports" (which can also be filtered by date) and each report's status and history. Reporters do not see measures or AI output.
- **Safety Officer:** works the incident queue (status tabs, search, category and colour filters, and an **Occurred on** date picker that shows every incident from one day). On an incident: **start review**, then severity and **analysis**, then the **AI draft**, which can be approved, edited, discarded or regenerated and updates on its own while generating. Then the **measures checklist**: Applied, or Not applied with a required reason; click MUST/SHOULD to change priority; add your own measures. Finally **close** the incident, with a preview of the colour it will close as. **After closing**, any Safety Officer can mark a measure that was not applied as **completed** (with a required note), for example when a part arrives weeks later. The incident stays closed, its colour updates, the original reason is kept, and the follow-up appears in the history. Also has the dashboard and the policy library.
- **Admin:** has the **safety overview**, with red / yellow / in-progress / green counts as filters and red first; each incident shows its short summary and ✅ ⚠️ ❌ counts. An **Occurred on** date picker shows one day's incidents, and the colour counts follow it. A **Completed after closing** switch shows incidents with late fixes. The incident view shows the issue, summary, suggested measures, applied measures (late fixes show the note, who and when) and not-applied measures with reasons. Also has the **dashboard**, the **policy library** (with a search showing which sections the AI would use), and **user management**: add users, change roles, reset passwords, deactivate or reactivate. Users are never deleted, so the audit trail stays complete. An admin can't deactivate or demote themselves, and the last active admin can't be removed.

## Rules the system enforces

**Statuses:** `submitted → under_review → measures_pending → closed`. No skipping and no going back. Every change is logged with who made it and when.

**Measures:** each one is `must` or `should`, and `pending`, `applied` or `not_applied`. A **reason is required** for `not_applied`. Once the incident is closed, measures are frozen except for one action: a Safety Officer can mark a `not_applied` measure as **completed after closing**, with a required note. Admins and reporters cannot.

**Incident colour** (calculated each time it's read, never stored):

| Colour | Rule | Measure icon |
|---|---|---|
| grey | no measures yet, or any measure still pending | ○ pending |
| red | any Must measure not applied | ❌ Must not applied |
| yellow | all Must applied, some Should not applied | ⚠️ Should not applied |
| green | every measure applied | ✅ applied |

**Closing** needs at least one measure, none pending, and the AI draft approved or discarded. A red incident **can** close, and it stays red on the admin overview.

## API overview

| Method | Path | Who |
|---|---|---|
| POST | `/api/auth/login` · GET `/api/auth/me` | everyone |
| POST | `/api/incidents` | any logged-in user |
| GET | `/api/incidents` (filters: status, category, severity, colour, airport, q, dates) | reporter: own only |
| GET | `/api/incidents/{id}` | reporter: own only |
| POST | `/api/incidents/{id}/start-review` | officer |
| POST | `/api/incidents/{id}/analysis` (severity + analysis; starts the AI job) | officer |
| PATCH | `/api/incidents/{id}/ai-summary` · POST `…/approve`, `…/discard`, `…/regenerate` | officer |
| POST | `/api/incidents/{id}/measures` (add own measure) | officer |
| PATCH | `/api/measures/{id}` (status, reason, priority) | officer |
| POST | `/api/measures/{id}/complete` (note; closed incidents, not-applied measures only) | any officer |
| POST | `/api/incidents/{id}/close` | officer |
| GET | `/api/admin/incidents` (red first, colour totals; filters: colour, status, category, `completed_late`, `date_from`, `date_to`) · `/api/admin/incidents/{id}` | admin |
| GET/POST | `/api/admin/users` · PATCH `/api/admin/users/{id}` · POST `/api/admin/users/{id}/reset-password` | admin |
| GET | `/api/dashboard/stats` | officer, admin |
| GET | `/api/policies` · `/api/policies/search?q=` · POST `/api/policies` (admin) | officer, admin |
| GET | `/api/meta/taxonomy` · `/api/health` | public |

**Date filters** (`date_from`, `date_to`) are ISO 8601 times **with a timezone**, compared with when the incident occurred. The frontend sends the start and end of the chosen day in the user's local time, so an incident at 00:30 IST on 10 Nov counts as 10 Nov.

The AI summary is generated in the background after `/analysis`. The frontend polls `GET /incidents/{id}` while `summary.status` is `"generating"`.

## How the AI works

1. **Query:** category + title + description + the officer's analysis.
2. **Retrieve:** cosine similarity over policy chunks with pgvector, with a boost for the policy matching the reported category.
3. **Generate:** Claude Haiku answers through a **forced tool call**, so the API returns a structured object (summary + 3–8 measures) instead of free text. The result is validated with Pydantic and retried once if invalid. Rate limits, overload and 5xx errors are retried with backoff; a wrong API key fails immediately.
4. **Grounding check:** any measure citing a policy chunk that wasn't retrieved is **dropped**, and the summary records how many were removed.
5. **Human in the loop:** the result is a *draft*. Nothing is official until the officer approves it. If the AI fails, the officer discards the draft and adds measures by hand.

`LLM_PROVIDER` can be `mock` (offline, default), `anthropic` or `openai`. `EMBEDDING_PROVIDER` can be `hash` (offline, keyword style, default) or `openai` (semantic). After changing the embedding provider, run `python -m app.seed --policies-only`.

## Tests and evaluation

```powershell
cd backend
python -m pytest -q                                   # 88 tests, uses the skyshield_test database
python -m scripts.evaluate_ai --provider anthropic    # AI metrics on 32 hand-written incidents
```

The tests cover every colour combination and that the SQL colour filter matches the Python rule; every role permission; invalid transitions and validation errors; the full workflow to yellow and to red; completing a measure after closing (any officer, note required, colour updates, original reason kept, admins refused); filtering by date (local-time day boundaries, both lists, colour totals, invalid ranges rejected); user management (deactivation blocks sign-in and existing tokens, role changes apply at once, admin lock-out protection, password reset); and the AI layer, using fake API responses so no key is needed: structured output, the validation retry, HTTP retry and backoff, the grounding check, safe failure and recovery of a stuck generation.

**Evaluation results** (32 hand-written incidents, deliberately worded differently from the dataset):

| Metric | Claude Haiku | Offline mock |
|---|---|---|
| Retrieval hit@3, text only | 90.6% | 90.6% |
| Retrieval hit@1, with reported category | 100% | 100% |
| Generation succeeded | **100%** | 100% |
| Measures grounded in retrieved policy | **100%** | 100% |
| Expected Must keywords found | 92.2% | 95.3% |
| Output has both Must and Should | 100% | 100% |

Retrieval is identical because it runs before the model. Keyword recall is a strict word match, so Haiku's rephrased measures (for example "inspect the door for damage" instead of "damage inspection") count as misses; it understates Haiku slightly.

## Git workflow

| Branch | Purpose |
|---|---|
| `main` | Stable, demo-ready code and tagged releases. Updated only by pull request from `develop` |
| `develop` | Integration branch. Feature branches merge here by pull request |
| `feature/<name>` | One branch per piece of work, created from `develop` and deleted after merge |

Commit messages follow the conventional style: `feat(scope): …`, `fix(scope): …`, `docs: …`, `test: …`. Never commit `backend\.env`.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `password authentication failed for user "skyshield"` | Something else answered on the database port, usually a local PostgreSQL. Check that `DATABASE_URL` in `.env` uses port **5433**, matching `docker-compose.yml` |
| `'vite' is not recognized` | Frontend packages aren't installed. Run `npm install` in `frontend` |
| `Could not read package.json` | Either you're in the wrong folder (`npm` runs in `frontend`, not `backend`) or you're on a branch without the frontend. Check with `git branch --show-current` |
| `Activate.ps1 cannot be loaded` | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal |
| AI summary shows **Failed** | Check the uvicorn terminal. A `401` means a wrong API key; `404` / model not found means set a model your account can use in `LLM_MODEL` |
| Coding assistants (Codex etc.) can't run Docker or `pip` | Their sandbox blocks Docker and network access. Run those commands in your own terminal |

## About the data

- **Everything is synthetic:** 185 incidents from Jan 2024 to Nov 2026, including 5 edge cases (a 200-character title, empty optional fields, a duplicate-looking title, Hindi text with special characters, and a minimal report). Airports and aircraft types are real; **operators are fictional**, so no record suggests an event at a real airline.
- **Categories** follow DGCA India's eight National High-Risk Categories (NASP 2024–2028) plus the other types DGCA tracks. **Severity** follows the AAIB India classification: accident, serious incident, incident.
- **The 17 policy documents are sample SOPs written for this project.** Their themes follow DGCA and ICAO material, but they are **not official regulatory text**. Before real use, replace them with approved SOPs and the official DGCA CARs (upload with `POST /api/policies`, using the same `## section` / `- MUST:` format).

## Known limits and next steps

- **No report export:** PDF/Excel exports for regulators are not built yet.
- **No self sign-up:** the admin creates every account.
- **Sessions:** tokens expire after 8 hours, but "log out" does not revoke them, and there is no login rate limiting yet.
- **Demo passwords:** every demo user shares `Password@123`; change them before any real use.
- **AI job:** runs inside the API process. If the server restarts mid-generation, the officer can regenerate after 2 minutes; a job queue would be the production step.
- **Offline mock:** it takes the first Must/Should lines of the matched policy, not necessarily the most relevant; the real model chooses per incident.
