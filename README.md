# Domain-Adaptive Churn Prediction Platform

**Upload your raw tables. It works out the schema, derives the features and scores churn — per vertical.**

[![Live prototype](https://img.shields.io/badge/live-churnsystem--two.vercel.app-6366f1)](https://churnsystem-two.vercel.app)
[![Tests](https://img.shields.io/badge/tests-56%20passing-059669)](#tests)

| | |
|---|---|
| **Live prototype** | **https://churnsystem-two.vercel.app** |
| **Project brief** | [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) |
| **Demo script** | [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) |
| **AI usage statement** | [docs/AI_USAGE.md](docs/AI_USAGE.md) |

## Try it in 30 seconds — no install, no API key

1. Open **https://churnsystem-two.vercel.app**
2. Enter any company name and pick a vertical (SaaS, Telecom or FinTech)
3. Click **Run the sample**

It scores 100 customers from the bundled dataset for that vertical and shows the
discovered schema, the churn drivers and a retention playbook per account. No
API key is required — the platform falls back to a deterministic offline engine
and tells you which engine produced the numbers.

Against the known churning cohort in the bundled data (25 of 100 per vertical),
the offline engine reaches **AUC 0.96–0.98**, putting **20–22 of the 25 real
churners in its top 25**, in under a tenth of a second.

## Features

- **Multi-Tenant Architecture**: Supports multiple business verticals with industry-specific schemas and churn risk factors.
- **Domain Adaptation**: Intelligent schema alignment and semantic understanding across different data formats.
- **Automated Ingestion**: Upload CSV/Excel datasets for automated validation and processing.
- **Analytics & Insights**: Churn risk calculation, key risk driver analysis, and retention recommendations.
- **Interactive UI & REST API**: Modern web dashboard built with FastAPI, Jinja2 templates, and responsive frontend components.

## Project Structure

```text
├── churn_platform/
│   ├── application/       # Use cases and DTOs
│   ├── domain/            # Entities and interfaces
│   ├── infrastructure/    # AI gateway, sector cores, parsers, repositories, sample catalog
│   ├── presentation/      # FastAPI routes, Jinja templates, static CSS/JS
│   └── main.py            # Application entrypoint
├── data/                  # Bundled mock datasets (FinTech, SaaS, Telecom)
├── generate_mock_data.py  # Mock dataset generator
├── requirements.txt       # Python dependencies
└── api_key.env.example    # Environment variable template
```

## Quick Start

### 1. Prerequisites
- Python 3.10+
- Git

### 2. Setup Virtual Environment
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements-dev.txt
```

`requirements.txt` holds runtime dependencies only — that is what the deployed
function installs. `requirements-dev.txt` adds pytest and watchfiles.

### 4. Configuration (optional)
A Qwen API key is **not required**. Without one the platform runs its
deterministic offline engine, which is what the live prototype demonstrates.

To enable the Qwen path:
```bash
cp api_key.env.example api_key.env
# then set DASHSCOPE_API_KEY in api_key.env
```

### 5. Generate Mock Data (Optional)
```bash
python generate_mock_data.py
```

### 6. Run the Application
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

`main.py` at the repository root re-exports the app, so `uvicorn main:app` and
`uvicorn churn_platform.main:app` are equivalent. No API key is needed — without
one the platform runs its offline engine.

Open your browser and navigate to:
- **Onboarding**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Dashboard**: [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
- **API Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/tenants/` | Register a workspace (name + sector) |
| `GET` | `/api/v1/tenants/{tenant_id}` | Confirm a workspace still exists — the repository is in-memory, so a restart invalidates every id |
| `GET` | `/api/v1/samples/{sector}` | Describe the mock dataset bundled for a sector |
| `GET` | `/api/v1/engine/status` | Which scoring engine will run, and why |
| `POST` | `/api/v1/upload/analyze` | Run the pipeline on uploaded CSV/Excel tables |
| `POST` | `/api/v1/upload/analyze-sample` | Run the same pipeline on the bundled sample dataset |
| `GET` | `/api/v1/analytics/metrics?tenant_id=` | Aggregates for the latest run: tier counts, mean probability, top drivers, channel mix |
| `GET` | `/api/v1/analytics/latest?tenant_id=` | The full stored result, so the dashboard survives a refresh |

### Notes

- On the Qwen path each entity costs one model call, so `/upload/analyze*` scores
  only the first 20 resolved entities (`MAX_ENTITIES` in
  `presentation/api/v1/upload.py`). The dashboard reports how many were skipped.
  The local engine has no such cost and scores up to 200.
- Tenants and analysis results are held in memory. Restarting the server clears
  both; the dashboard detects this and returns you to onboarding.

## Deploying to Vercel

Live at **https://churnsystem-two.vercel.app**, deployed automatically on every
push to `main`.

Vercel has first-class FastAPI support: it builds the ASGI app as one function
with a catch-all route that preserves the request path. It only needs to find
the app, and `churn_platform/main.py` is not a location it checks, so `main.py`
at the repository root re-exports it.

Do not reach for `vercel.json` rewrites here. A rewrite replaces the path the
function receives, so every request arrives at FastAPI as `/api/index` and gets
FastAPI's own 404. Declaring the entrypoint in `pyproject.toml` also works but
switches dependency installation from `requirements.txt` to `uv lock`, which
then needs a `[project]` table.

Two things were needed to make it correct on serverless, where consecutive
requests routinely land on different instances:

- **Tenants are stateless.** The workspace id encodes the name and sector
  (`StatelessTenantRepository`), so any instance can resolve a workspace without
  a shared store. Sector is re-validated on decode.
- **The last analysis is cached in the browser.** The server still keeps it in
  memory, but that copy may not survive to the next request, so the dashboard
  falls back to the viewer's own copy when the server returns `204`.

Set `DASHSCOPE_API_KEY` in the Vercel project's environment variables to enable
the Qwen path. Without it the deployment runs on the local engine, which needs
no network access and no key.

## Tests

```bash
pytest
```

56 tests, none touching the network. Feature tests use hand-built DataFrames with
hand-computable expected values rather than the generated fixtures — asserting
against generated data only proves the two agree, not that either is right.

Config lives in `pytest.ini`, not `pyproject.toml`: adding a `pyproject.toml`
makes Vercel's Python build switch from `requirements.txt` to `uv lock`, which
then fails for want of a `[project]` table.

## Ingestion

CSV and Excel are both accepted. A workbook is expanded sheet by sheet, each
becoming its own table named `workbook.xlsx::SheetName`, so one `.xlsx` can carry
everything a CSV user would upload as separate files. One unreadable file among
several is reported and skipped rather than failing the request.

## Features

The synthesizer is sector-agnostic — it sees a `SchemaMapping`, not a vertical —
and emits per child table: row counts, recency, rolling 7d/30d windows, an
activity velocity comparing the last week against the prior month, a failure rate
from status-like columns, and a keyword churn score from free text.

Recency is anchored to `max(timestamp)` in the data, never the wall clock, so
fixtures frozen at a reference date stay meaningful however long afterwards they
are read.

`sector_feature_enrichers` then adds vertical-specific maths as a post-step:
balance drain and P2P failure streaks (FinTech), recharge cadence (Telecom),
export ratio (SaaS).

## Scoring engines

The platform ships with two interchangeable engines behind the same interfaces,
so it is fully functional with or without an API key.

| Engine | Schema resolution | Scoring | Needs a key |
| --- | --- | --- | --- |
| `qwen` | `AISchemaResolver` | `SaasCore` / `TelecomCore` / `FintechCore` | Yes |
| `local` | `HeuristicSchemaResolver` | `LocalChurnCore` | No |

`POST /upload/analyze*` accepts an `engine` form field:

- **`auto`** (default) — try Qwen, fall back to the local engine if the key is
  missing or the call fails. The response reports which engine ran in `engine`,
  and why it fell back in `engine_reason`. After a failure Qwen is skipped for
  two minutes so every later request does not pay for a call known to fail.
- **`qwen`** — Qwen only. Failures return `502` instead of falling back.
- **`local`** — never call the model.

Set the process-wide default with `CHURN_ENGINE=auto|qwen|local`.

### The local engine

`LocalChurnCore` reads the *names* of the synthesized features to decide what
each one means — recency, engagement volume, grievance volume, failure counts,
monetary value — then ranks every entity against the rest of the cohort. Nothing
is hard-coded to one dataset, so it adapts to whatever tables are uploaded, and
each score carries the drivers that produced it.

Because it makes no API calls it scores the whole cohort (up to 200 entities)
rather than the 20-entity batch the Qwen path is capped at.

## Mock data

`generate_mock_data.py` does not emit uniform noise. Each entity is assigned a
latent risk level first, and its behaviour is generated conditionally: at-risk
entities go quiet, complain more, fail payments, and drift towards competitors.

That makes the fixtures worth analysing. Measured against the latent risk the
generator used, the local engine reaches a Spearman correlation of **+0.82 to
+0.91** across the three sectors.

```bash
python generate_mock_data.py
```

## Dashboard

- Dark and light themes, following the system preference and remembered per browser.
- Drag-and-drop ingestion, or one click to run the bundled sample dataset.
- Risk-tier and probability-band charts, churn-driver frequency, and channel/action mix.
- Per-sector KPI cards at `/dashboard/{sector}`: MRR at risk, login velocity and
  feature drop-off (SaaS); dropped-call rate, port-out enquiries and worst region
  (Telecom); liquidity drain, dormant accounts and P2P failure streaks (FinTech).
- Searchable, sortable, paginated at-risk table with per-account retention playbooks.
- Keyboard: `/` focuses search, `←`/`→` page through playbooks, `Esc` closes the drawer.
- An engine badge names the engine that produced the current results, and the
  Auto / Qwen / Local selector overrides it per run.
