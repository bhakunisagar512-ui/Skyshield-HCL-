# SkyShield: Aviation Safety and Incident Reporting

SkyShield is an incident reporting system for an airline safety department. Anyone can report an occurrence. A Safety Officer reviews it and writes an analysis. The AI reads that analysis against the company's policy documents and suggests **Must** and **Should** measures, each with a citation. The officer marks every measure as applied or not applied, and the admin sees each incident colour-coded by how well it was handled.

```
Report → Review & analyse → AI summary + measures → Mark measures → Close → Admin panel
```

The repository has three parts: the **backend** (FastAPI), the **frontend** (React) and the **dataset**.

## Contents

```
skyshield/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app, routers mounted under /api
│   │   ├── config.py            settings from .env
│   │   ├── database.py          engine, session, consistent_read()
│   │   ├── models.py            SQLAlchemy tables
│   │   ├── schemas.py           Pydantic request/response models + validation
│   │   ├── seed.py              loads database/ into Postgres
│   │   ├── core/                taxonomy, JWT + bcrypt, role dependencies
│   │   ├── routers/             auth, incidents, measures, admin, dashboard, policies
│   │   └── services/
│   │       ├── status_rules.py  colour rule, icons, allowed transitions (single source of truth)
│   │       ├── workflow.py      transitions, history, AI background job
│   │       ├── serialize.py     API shapes + SQL mirror of the colour rule
│   │       ├── policies.py      ingest policy → chunks → embeddings
│   │       └── ai/              embeddings, LLM providers, RAG pipeline
│   ├── alembic/                 migrations
│   ├── scripts/evaluate_ai.py   retrieval + generation evaluation
│   └── tests/                   70 pytest tests
├── frontend/                    React 18 + Vite + Bootstrap 5 + Recharts
│   └── src/
│       ├── api.js, auth.jsx     API client (JWT), login state
│       ├── components/          layout, colour pill, badges, measure icons
│       └── pages/               login, report form, incident list + detail (officer workflow),
│                                dashboard, admin/ (overview, incident, users, policies)
├── database/
│   ├── generate_dataset.py      creates data/*.csv (seeded, reproducible)
│   ├── data/                    users, incidents, measures, ai_summaries, status_history
│   ├── policies/                17 SOP documents used by the AI
│   └── eval/eval_set.json       32 hand-written incidents with expected answers
└── docker-compose.yml           Postgres 16 + pgvector
```

## Run it

You need Python 3.11+ and Docker (or a local Postgres 16 with the pgvector extension).

```bash
# 1. database
docker compose up -d db

# 2. backend
cd backend
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # then set JWT_SECRET
alembic upgrade head
python -m app.seed --reset                           # loads data + indexes policies
uvicorn app.main:app --reload
```

Interactive API docs: http://localhost:8000/docs

```bash
# 3. frontend (needs Node.js 18+), in a second terminal
cd frontend
npm install
npm run dev                                          # http://localhost:5173
```

The frontend forwards `/api` to the backend on port 8000, so both must be running. The login page has buttons that fill in the demo accounts.

### Screens by role

- **Reporter:** report form (with validation), "My reports", and each report's status and history. Reporters do not see measures or AI output.
- **Safety Officer:** incident queue with status tabs and filters. On the incident page: start review, then severity + analysis, then the AI draft (approve, edit, discard or regenerate; it refreshes automatically while generating). Then the measures checklist: Applied, or Not applied with a required reason; click a MUST/SHOULD badge to change priority; add your own measures. Last, close the incident, with a preview of the colour it will close as. Also the dashboard and the policy library.
- **Admin:** safety overview with red / yellow / in-progress / green totals as filters, red first; each incident shows its short summary and ✅ ⚠️ ❌ counts. The incident view shows the issue, summary, suggested measures, applied measures and not-applied measures with reasons. Also the dashboard, user management and the policy library with a search that shows which sections the AI would use.

Check the whole flow including the AI with the server running: `python -m scripts.smoke_test`

If your database runs on a different port (for example 5433 because a local PostgreSQL already uses 5432), change `DATABASE_URL` in `.env`. The tests follow it automatically.

To regenerate the dataset (optional, the CSVs are already committed): `python database/generate_dataset.py`

### Demo logins (password `Password@123`, development only)

| Role | Email |
|---|---|
| Admin | admin@skyshield.example |
| Safety Officer | arjun.mehta@skyshield.example (also kavya.reddy@, sanjay.bose@) |
| Reporter | ananya.iyer@skyshield.example (12 reporters in total) |

## Rules the system enforces

**Statuses:** `submitted → under_review → measures_pending → closed`. You can't skip a step or go backwards. Every change is logged in the status history.

**Measures:** each one is `must` or `should`, and `pending`, `applied` or `not_applied`. A **reason is required** for `not_applied`. Measures are frozen once the incident is closed.

**Incident colour** (calculated each time it's read, never stored):

| Colour | Rule |
|---|---|
| grey | no measures yet, or any measure still pending |
| red | any Must measure not applied |
| yellow | all Must applied, some Should not applied |
| green | every measure applied |

**Measure icons:** tick = applied, exclamation = Should not applied, cross = Must not applied.

**Closing** needs at least one measure, none pending, and the AI draft approved or discarded. A red incident **can** close, and it stays red on the admin panel.

**Roles:** Reporters create incidents and see only their own. Safety Officers run the workflow. Admins have read-only access to incidents and manage users and policies.

## API overview

| Method | Path | Who |
|---|---|---|
| POST | `/api/auth/login`, GET `/api/auth/me` | everyone |
| POST | `/api/incidents` | any logged-in user |
| GET | `/api/incidents` (filters: status, category, severity, colour, airport, q, dates) | reporter: own only |
| GET | `/api/incidents/{id}` | reporter: own only |
| POST | `/api/incidents/{id}/start-review` | officer |
| POST | `/api/incidents/{id}/analysis` (severity + analysis, starts the AI job) | officer |
| PATCH | `/api/incidents/{id}/ai-summary`, POST `.../approve`, `.../discard`, `.../regenerate` | officer |
| POST | `/api/incidents/{id}/measures` (add own measure) | officer |
| PATCH | `/api/measures/{id}` (status, reason, priority) | officer |
| POST | `/api/incidents/{id}/close` | officer |
| GET | `/api/admin/incidents` (sorted red → yellow → grey → green, colour totals), `/api/admin/incidents/{id}` | admin |
| GET/POST | `/api/admin/users` | admin |
| GET | `/api/dashboard/stats` | officer, admin |
| GET | `/api/policies`, `/api/policies/search?q=` · POST `/api/policies` (admin) | officer, admin |
| GET | `/api/meta/taxonomy`, `/api/health` | public |

The AI summary is generated in the background after `/analysis`. The frontend should poll `GET /incidents/{id}` while `summary.status == "generating"`. It usually takes under a second with the mock provider, and a few seconds with a real LLM.

## AI: how it works

1. **Query:** category + title + description + the officer's analysis.
2. **Retrieve:** cosine similarity on policy chunks (pgvector), with a boost for the policy that matches the reported category.
3. **Generate:** a summary plus 3–8 measures, validated with Pydantic. With Anthropic the model must answer through a forced tool call, so the API returns a structured object instead of free text. If validation still fails, the request is retried once with the error explained. Rate limits, overload and 5xx errors are retried with backoff.
4. **Grounding check:** any measure citing a chunk that wasn't retrieved is **dropped**, and the summary records how many were removed.
5. **Human in the loop:** the result is a *draft*. Nothing is official until the officer approves it. If the AI fails, the officer discards the draft and adds measures by hand.

Set `LLM_PROVIDER` in `.env`:

- `mock` (default): runs offline. It pulls the MUST/SHOULD lines from the best-matching policy. Good for development, tests and demos without an API key.
- `anthropic` or `openai`: a real model, using the same pipeline and grounding check. The default Anthropic model is `claude-haiku-5-5`, the cheapest; set `LLM_MODEL` to use another.

`EMBEDDING_PROVIDER=hash` is an offline keyword-style embedder. `openai` gives semantic embeddings. After switching, re-run `python -m app.seed --policies-only`.

## Tests and evaluation

```bash
cd backend
pytest -q                          # 70 tests; uses the skyshield_test database
python -m scripts.evaluate_ai      # retrieval + generation metrics on 32 hand-written cases
```

The tests cover every colour combination; structured output, the validation retry and HTTP retry/backoff (all with fake API responses, so no key is needed); the SQL colour filter agreeing with the Python rule; every role permission; invalid transitions; validation errors; the full workflow to yellow and to red; grounding (a fake LLM citing a non-existent chunk is rejected); invalid LLM output failing safely; and a stuck generation being retried after a timeout.

Evaluation results with the offline providers (`mock` + `hash`):

| Metric | Result |
|---|---|
| Retrieval hit@1, text only | 75.0% |
| Retrieval hit@3, text only | 90.6% |
| Retrieval hit@1, with reported category | 100% |
| Measures grounded in retrieved policy | 100% |
| Expected MUST keywords found | 95.3% |

The text-only misses happen because keyword embeddings can't tell, for example, "cardiac arrest" (medical) from general reporting rules. Semantic embeddings (`EMBEDDING_PROVIDER=openai`) should close most of that gap. Re-run the evaluation after switching to confirm.

## About the data

- **Everything is synthetic.** There are 185 incidents from Jan 2024 to Nov 2026, including 5 edge cases (a 200-character title, empty optional fields, a duplicate-looking title, Hindi text with special characters, and a minimal report). Airports and aircraft types are real; **operators are fictional**, so no record suggests an event at a real airline.
- **Categories** follow DGCA India's eight National High-Risk Categories (NASP 2024–2028), plus the other types DGCA tracks. **Severity** follows the AAIB India classification: accident, serious incident, incident.
- **The 17 policy documents are sample SOPs written for this project.** Their themes follow DGCA/ICAO material, but they are **not official regulatory text**. Before real use, replace them with your organisation's approved SOPs and the official DGCA CARs (upload with `POST /api/policies`, in the same `## section` / `- MUST:` format).

## Known limits

- The AI job runs inside the API process (FastAPI BackgroundTasks). If the server restarts during generation, the officer can regenerate after 2 minutes. A job queue would be the next step for production.
- The mock provider picks the first Must/Should lines of the matched policy, not necessarily the most relevant ones. A real LLM chooses per incident.
