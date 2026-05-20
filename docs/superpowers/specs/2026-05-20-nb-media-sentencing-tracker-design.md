# NB Media — US Homicide Sentencing Tracker

**Status:** Design draft
**Date:** 2026-05-20
**Owner:** NB Media Productions (ai.nbmediaa@gmail.com)

---

## 1. Problem

NB Media wants to systematically file public-records requests (federal FOIA and state equivalents) on US homicide cases that have just been sentenced, so the records can be turned into editorial content. Today this work is ad-hoc — researchers find cases manually from news, with no consistent pipeline. There is no single national database of US sentencings; the system must aggregate across federal, state, and local sources.

## 2. Goals

- Capture **≥95% of US homicide/murder sentencings that receive any English-language news coverage**, daily.
- Surface each captured case to researchers in a single web inbox with all fields needed to file public-records requests (defendant, victim, county, court, judge, docket, charges, sentence, investigating police agency, prosecuting office).
- Let researchers triage cases, mark them for FOIA filing, and (Phase C) file records requests through MuckRock from inside the app.
- Track the full lifecycle: case detected → reviewed → records requested → records received → archived.
- Be runnable and maintainable by a small in-house engineering team on a single VPS.

## 3. Non-goals

- A complete database of every US sentencing. Many state/local cases never appear in news; those are out of scope.
- Real-time alerting (sub-hour latency). Daily + half-day batches are sufficient.
- A public-facing product. Internal NB Media staff only (domain-restricted login).
- General crime tracking (charges, arrests, trials). Only **sentencing events** for homicide/murder.
- Building our own FOIA-filing service. We use MuckRock's API.

## 4. Users

| Role | Count | What they do |
|---|---|---|
| Researcher | 5–15 | Reviews daily inbox, approves/rejects cases, enriches missing fields, files records requests |
| Admin | 1–2 | Manages users, monitors source health, tunes ingestion |

All users must authenticate with a Google account at `@nbmediaproductions.com`.

## 5. Phased delivery

The system ships in three phases. Each phase is a usable release.

| Phase | Scope | Engineering effort |
|---|---|---|
| **A — Inbox Reviewer** | Backend pipeline + database + inbox UI + case detail + source health. Researcher approves/rejects. FOIA filed manually on MuckRock website. | 3–4 weeks |
| **B — Enrichment** | Auto-enrichment (docket #, judge, investigating PD) via SerpAPI + CourtListener. Manual enrichment UI for low-confidence fields. | +2–3 weeks |
| **C — FOIA Integration** | MuckRock API filing inside the app. State-specific templates. Response tracking. Records ingestion. | +4–6 weeks |

Total to full Phase C: ~10–13 weeks.

## 6. High-level architecture

```
                Researcher's browser (HTTPS)
                          │
                          ▼
              ┌───────────────────────┐
              │   Caddy (auto-SSL)    │
              └───────┬───────┬───────┘
                      │       │
                ┌─────▼──┐  ┌─▼──────────┐
                │Next.js │  │  FastAPI   │
                │frontend│◄►│  backend   │
                └────────┘  └──┬─────────┘
                               │
                  ┌────────────┼──────────────┐
                  ▼            ▼              ▼
              ┌─────────┐  ┌───────┐  ┌──────────────┐
              │Postgres │  │ Redis │  │Celery workers│
              │   16    │  │   7   │  │ + Beat sched │
              └─────────┘  └───────┘  └──────┬───────┘
                                             │
                                             ▼
                         External APIs (NewsAPI, MediaStack,
                         GDELT, DOJ, CourtListener, Claude,
                         MuckRock, Google OAuth, SerpAPI)
```

All services run natively on a single Ubuntu 22.04 VPS (no Docker). Deploys via `git pull` + `scripts/deploy.sh` which installs Python/Node deps, runs DB migrations, builds the frontend, and restarts systemd services.

## 7. Tech stack

- **Backend:** Python 3.11+, FastAPI (HTTP), Celery (background jobs), SQLAlchemy + Alembic (ORM + migrations), Pydantic v2 (schemas).
- **Frontend:** Next.js 14+ (App Router), React, TypeScript, Tailwind CSS, shadcn/ui components.
- **Database:** Postgres 16.
- **Queue / cache:** Redis 7.
- **Reverse proxy + TLS:** Caddy (already installed on the VPS).
- **Auth:** Google OAuth 2.0 with `hd=nbmediaproductions.com` hosted-domain restriction. JWT session cookies (HttpOnly, Secure, SameSite=Lax).
- **LLM:** Claude Haiku 4.5 for extraction (fast, cheap), Claude Sonnet 4.6 for low-confidence re-extractions and Phase C template generation.
- **Observability:** Sentry (errors), structured logs to file + journalctl, simple health-check endpoint.
- **Backups:** Nightly `pg_dump` pushed to Backblaze B2 (S3-compatible) with 30-day retention.

## 8. Data model

### 8.1 Core tables (Phase A)

**`users`**
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| email | text unique | must end in `@nbmediaproductions.com` |
| full_name | text | from Google profile |
| role | enum | `admin` \| `researcher` |
| google_sub | text unique | OAuth subject id |
| created_at | timestamptz | |
| last_login_at | timestamptz | |
| is_active | bool | default true |

**`cases`** — one row per unique homicide sentencing
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| defendant_name | text | |
| defendant_name_normalized | text | lowercase, punctuation stripped — used for dedup matching; generated column or maintained on insert/update |
| defendant_age | int | nullable |
| defendant_hometown | text | nullable |
| victims | jsonb | `[{name, age}, ...]` |
| charges | jsonb | `[{statute, degree, description}, ...]` |
| sentence_text | text | raw "Life without parole", "45 years to life", etc. |
| sentence_years | int | parsed numeric, null if life/death |
| sentence_type | enum | `years` \| `life` \| `life_no_parole` \| `death` |
| sentencing_date | date | |
| court_name | text | |
| county | text | critical for FOIA targeting |
| state | char(2) | |
| docket_number | text | nullable (often missing, filled in Phase B) |
| judge_name | text | nullable |
| prosecuting_office | text | |
| investigating_agency | text | nullable, filled in Phase B |
| summary | text | one-paragraph LLM summary |
| content_score | int | 1–5, auto-flagged for editorial value |
| status | enum | `new` \| `reviewing` \| `approved` \| `rejected` \| `foia_filed` \| `records_received` \| `archived` |
| reviewed_by | uuid fk users | nullable |
| reviewed_at | timestamptz | nullable |
| notes | text | researcher notes |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**`articles`** — every source mention of a case (many-to-one with cases)
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| case_id | uuid fk cases | nullable until matched |
| source_id | uuid fk sources | |
| source_name | text | denormalized for fast queries |
| source_type | enum | `news_api` \| `gdelt` \| `doj` \| `da_office` \| `courtlistener` \| `google_alert` |
| url | text unique | |
| published_at | timestamptz | |
| title | text | |
| raw_text | text | full article text |
| extracted_json | jsonb | full LLM extraction output |
| extraction_status | enum | `pending` \| `extracted` \| `failed` \| `no_match` |
| extraction_model | text | e.g. `claude-haiku-4-5`, stored so we can re-run when prompt changes |
| extraction_error | text | nullable, debug aid |
| created_at | timestamptz | |

**`sources`** — ingestion source registry + health
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| name | text | |
| type | enum | `news_api` \| `rss` \| `scraper` \| `api` \| `webhook` |
| config | jsonb | API key reference, search terms, URLs to scrape |
| last_run_at | timestamptz | |
| last_success_at | timestamptz | |
| items_fetched_24h | int | |
| items_extracted_24h | int | |
| consecutive_failures | int | for health alerting |
| is_active | bool | default true |

### 8.2 Phase B additions

**`enrichments`** — per-field enrichment attempts (auto + manual)
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| case_id | uuid fk cases | |
| field | text | `docket_number` \| `judge_name` \| `investigating_agency` \| ... |
| value | text | |
| source | enum | `llm` \| `serpapi` \| `courtlistener` \| `researcher_manual` |
| source_url | text | nullable |
| confidence | numeric(3,2) | 0.00–1.00 |
| filled_by | uuid fk users | null if automated |
| filled_at | timestamptz | |

### 8.3 Phase C additions

**`foia_requests`** — each records request filed via MuckRock
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| case_id | uuid fk cases | |
| agency_name | text | |
| agency_type | enum | `police` \| `da` \| `court_clerk` \| `medical_examiner` \| `dispatch` |
| muckrock_request_id | text | MuckRock internal id |
| status | enum | `draft` \| `submitted` \| `acknowledged` \| `fulfilled` \| `rejected` \| `no_response` |
| template_used | text | name of state-specific template |
| filed_by | uuid fk users | |
| filed_at | timestamptz | |
| records_received_at | timestamptz | nullable |
| records_url | text | MuckRock attachment URL |
| fees_charged | numeric(10,2) | |

**`audit_log`** — who-did-what
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk users | |
| action | text | `case_approved` \| `foia_filed` \| `case_rejected` \| ... |
| entity_type | text | `case` \| `foia_request` \| `user` |
| entity_id | uuid | |
| metadata | jsonb | |
| created_at | timestamptz | |

### 8.4 Indexes

- `cases (status, sentencing_date desc)` — inbox query
- `cases (state, county)` — geographic filters
- `cases (defendant_name_normalized, sentencing_date, state)` — dedup lookup
- `articles (case_id)` — load all sources for a case
- `articles (url)` unique — source-level dedup
- `articles (extraction_status, created_at)` — worker queue scans

## 9. Pipeline design

Pipeline runs on Celery. Beat scheduler triggers:
- Full sweep at 06:00 UTC daily
- Light sweep every 30 minutes 14:00–22:00 UTC (US business hours)

### 9.1 Step 1 — Ingest

Parallel workers per source. Each writes raw articles into `articles` with `extraction_status='pending'`.

- **NewsAPI.org** — query `("sentenced to life" OR "sentenced to death" OR "convicted of murder" sentenced OR "life without parole")` filtered to US English sources, last 24h.
- **MediaStack** — same query patterns, complementary coverage.
- **GDELT 2.0** — event-code filter for sentencing + actor type homicide, US-only.
- **DOJ press releases** — RSS from `justice.gov/news/press-releases` and 94 USAO RSS feeds, filter for sentencing language.
- **County DA scrapers** — registered per-source scrapers for ~30 county DA sites (LA, Cook, Harris, Manhattan, etc.). Each scraper is a Celery task with retry + backoff.
- **CourtListener webhook** — federal docket sentencing events.

Idempotency: every article keyed on `url` unique. Re-ingesting the same URL is a no-op.

### 9.2 Step 2 — Extract

For each article with `extraction_status='pending'`:

1. LLM call to Claude Haiku 4.5 with a structured-output prompt (JSON schema).
2. Output validated: must include defendant_name, sentencing_date, US state, homicide-related charge. If validation fails → mark `no_match`.
3. Successful output stored in `extracted_json`, status set to `extracted`.
4. Extraction model + prompt version stored alongside, so re-runs are possible when prompt evolves.
5. Cost: ~$0.001 per article at Haiku rates, ~$30/month at expected volume.

### 9.3 Step 3 — Dedup & link

For each newly-extracted article:

1. Normalize defendant name (lowercase, strip punctuation, collapse whitespace).
2. Query `cases` for match on `(normalized_defendant_name, sentencing_date ± 3 days, state)`.
3. If match → set `articles.case_id` to existing case; merge any new fields from this article into the case (only fill empty fields, don't overwrite).
4. If no match → create new `cases` row from this article's extraction, link the article.

### 9.4 Step 4 — Auto-enrich (Phase B)

For each new case missing critical FOIA fields (`docket_number`, `judge_name`, `investigating_agency`):

1. SerpAPI search: `"<defendant name> arrested <state>"` to find investigating agency.
2. CourtListener lookup for federal cases.
3. State-specific court website scrapers where feasible (low priority — many states have brittle systems).
4. Store result in `enrichments` with a confidence score.
5. If confidence ≥ 0.7 → write to `cases` directly. Else → leave for manual enrichment in UI.

### 9.5 Step 5 — Score & notify

Auto-score `content_score` 1–5 based on:
- Sentence severity (life/death = +1)
- Number of victims (>1 = +1)
- Mass-casualty / public-figure flags (LLM-tagged from article = +1)
- Unusual modus operandi flags (LLM-tagged = +1)
- Child victim (LLM-tagged = +1)

Send morning summary to researchers via Slack webhook + email: "23 new cases, 5 high-priority. [link]".

### 9.6 Step 6 — Health check

After each pipeline run:
- Update `sources.last_run_at`, `items_fetched_24h`, `items_extracted_24h`.
- If any source has `items_fetched_24h = 0` for 3 consecutive days → alert admin via email.
- Sentry captures any exceptions in workers.

### 9.7 Weekly recall eval

A separate weekly task samples random US homicide sentencings from external sources (Law&Crime, ProPublica's data, etc.) and checks whether they exist in our database. Logs recall percentage. Goal: ≥95%.

## 10. Webapp screens (Phase A)

Designed for non-technical researchers. Tailwind + shadcn/ui = clean, modern, accessible defaults.

### 10.1 `/login`
- Single "Sign in with Google" button.
- OAuth uses `hd=nbmediaproductions.com` parameter — Google only allows accounts in that domain.
- Backend additionally validates `email.endswith('@nbmediaproductions.com')`.
- On first sign-in, user is auto-created with `role='researcher'` unless email is in admin allowlist (env var).

### 10.2 `/inbox` (default landing page)
- Top bar: today's new-case count, pending review count, user menu.
- Filters: state, sentence type, content score, status, search by defendant name.
- Sorted by content score desc, then sentencing date desc.
- Each row: star rating, defendant name/age/location, sentence, charge, county+date, click → case detail.
- Pagination, 25 per page.

### 10.3 `/case/<id>` (case detail)
- **Left column:** all extracted fields, inline-editable (researcher can correct LLM mistakes).
- **Right column:** list of source articles, each linkable, with title and outlet.
- **Bottom action bar:** `Approve` / `Reject` / `Needs more info` buttons. Notes textarea.
- **Phase C addition:** "File records requests" button → opens filing wizard.

### 10.4 `/sources` (admin only)
- Table of every source, with last run, items in 24h, status indicator (green/yellow/red).
- Manual "Run now" button per source.
- Edit source config (search terms, etc.) in a side panel.

### 10.5 `/users` (admin only)
- List of researchers + last login + role.
- Activate / deactivate toggle.
- Promote to admin / demote to researcher.

## 11. Auth & permissions

- Google OAuth 2.0 with `hd` hosted-domain parameter.
- Server-side validation re-checks `email.endswith('@nbmediaproductions.com')` on every login.
- Session = JWT in HttpOnly + Secure + SameSite=Lax cookie, 7-day expiry, refreshed on activity.
- Two roles:
  - `researcher` — read all cases, edit assigned cases, file FOIAs.
  - `admin` — researcher rights plus user management + source management.
- Every state-changing action logged in `audit_log`.

## 12. Deployment

Single VPS, Ubuntu 22.04, ≥4 vCPU / 8 GB RAM recommended.

### 12.1 One-time setup

```
- Install: python3.11, nodejs 20, postgresql 16, redis 7, caddy, git
- Create non-root user `nbtool`, give it `/opt/nbtool` ownership
- Set up Postgres user + database
- Configure Caddy with research.nbmediaproductions.com → reverse proxy
- Place .env files (not in git) with secrets:
    DATABASE_URL, REDIS_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    ANTHROPIC_API_KEY, NEWSAPI_KEY, MEDIASTACK_KEY, SERPAPI_KEY,
    MUCKROCK_KEY (Phase C), SENTRY_DSN, BACKBLAZE_KEY
- Install systemd unit files from deploy/
- Initial git clone of repo to /opt/nbtool
```

### 12.2 Repo layout

```
/opt/nbtool/
├── backend/                 FastAPI + Celery (Python venv)
│   ├── app/
│   │   ├── api/             HTTP routes
│   │   ├── models/          SQLAlchemy models
│   │   ├── schemas/         Pydantic schemas
│   │   ├── workers/         Celery tasks
│   │   ├── sources/         per-source ingestion code
│   │   ├── extraction/      LLM extraction logic + prompts
│   │   ├── enrichment/      Phase B enrichment logic
│   │   ├── foia/            Phase C MuckRock integration
│   │   └── auth/            Google OAuth
│   ├── alembic/             DB migrations
│   ├── tests/
│   └── requirements.txt
├── frontend/                Next.js
│   ├── src/
│   │   ├── app/             App Router pages
│   │   ├── components/
│   │   └── lib/
│   └── package.json
├── deploy/
│   ├── systemd/             unit files
│   ├── Caddyfile.example
│   └── env.example
└── scripts/
    ├── deploy.sh            git pull + deps + migrate + build + restart
    ├── backup.sh            pg_dump + push to B2
    └── eval-recall.sh       weekly recall check
```

### 12.3 systemd services

- `nbtool-api.service` — uvicorn FastAPI
- `nbtool-frontend.service` — Next.js production server
- `nbtool-worker.service` — Celery worker
- `nbtool-beat.service` — Celery Beat scheduler

All restart automatically on failure. Logs to journalctl.

### 12.4 Deploy flow

```
ssh nbtool@vps
cd /opt/nbtool
git pull
./scripts/deploy.sh
```

`deploy.sh` does: install Python deps (`pip install -r backend/requirements.txt`), install Node deps (`pnpm install --frozen-lockfile`), run migrations (`alembic upgrade head`), build frontend (`pnpm build`), restart all four systemd services, run health check.

### 12.5 Backups

`scripts/backup.sh` runs nightly via cron:
1. `pg_dump` of the database to gzipped file
2. Push to Backblaze B2 with date-stamped filename
3. Delete local copies older than 7 days
4. Retain B2 copies for 30 days

## 13. Cost estimate

| Item | Monthly |
|---|---|
| News API (NewsAPI or MediaStack mid tier) | $50–250 |
| LLM (Claude Haiku 4.5 + occasional Sonnet) | $30–100 |
| VPS — already owned | $0 (sunk) |
| Backblaze B2 backups | $1–5 |
| Sentry (free tier) | $0 |
| Domain | $1–2 |
| SerpAPI (Phase B) | $50 |
| MuckRock Pro (Phase C) | $40 + per-request fees |
| **Total Phase A** | **~$130–360** |
| **Total Phase C (full)** | **~$270–700** |

FOIA filing fees themselves (paid to agencies for records) are separate and scale with usage: realistically $600–3,000/month at 30–60 filings/month.

## 14. Risks & mitigations

| Risk | Mitigation |
|---|---|
| News scrapers break when sites change | Per-source health monitoring + alerts; LLM extraction is the same code regardless of source |
| LLM extraction quality drifts | Weekly recall eval; raw articles + prompt version stored so we can re-extract everything |
| Single VPS = single point of failure | Daily off-site backups; can restore to a new VPS in <2 hours |
| Costs balloon if pipeline loops | Per-source rate limits + daily cost cap on LLM calls |
| Researcher abandons the tool | Phase A ships in 3–4 weeks with real value; feedback loop into Phase B design |
| Cases missed entirely | Recall eval surfaces gaps; new sources can be added without touching pipeline core |

## 15. Open questions for engineering kickoff

1. Exact VPS specs and current OS version — confirm before installation begins.
2. Which news API to subscribe to first (NewsAPI vs MediaStack vs Event Registry). Recommend a 2-week trial of each on a real workload before committing.
3. Initial list of county DA sites to scrape — top 30 by homicide volume? Or top 30 by NB Media's editorial coverage area?
4. Sentry vs. self-hosted error tracking.
5. Should `audit_log` retention have a TTL or be infinite?
6. Phase B confidence threshold for auto-fill — start at 0.7, tune from data.

## 16. Future / out of scope

- Mobile-responsive UI (Phase A is desktop-only).
- Multi-language source ingestion (Spanish-language US news).
- Auto-drafting editorial scripts from received records (LLM-assisted).
- Integration with NB Media's existing content management system.
- Public-facing case database (with redaction layer).
