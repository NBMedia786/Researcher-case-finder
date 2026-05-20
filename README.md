# NB Media Sentencing Tracker

A self-hosted webapp that aggregates US homicide sentencings daily from news APIs, DOJ, and DA sites, extracts FOIA-ready fields with an LLM, deduplicates across outlets, and presents the cases in a researcher inbox for review.

- Spec: [docs/superpowers/specs/2026-05-20-nb-media-sentencing-tracker-design.md](docs/superpowers/specs/2026-05-20-nb-media-sentencing-tracker-design.md)
- Plan: [docs/superpowers/plans/2026-05-20-nb-media-sentencing-tracker-phase-a.md](docs/superpowers/plans/2026-05-20-nb-media-sentencing-tracker-phase-a.md)

---

## Prerequisites

- Ubuntu 22.04+ VPS (1 CPU / 2 GB RAM minimum)
- Python 3.12
- Node.js 20 + pnpm
- PostgreSQL 16
- Redis 7
- Caddy 2
- Backblaze B2 CLI (`b2`) for backups (optional)

---

## One-Time VPS Setup

```bash
# As root:
adduser --system --group --home /opt/nbtool nbtool
chown -R nbtool:nbtool /opt/nbtool

# Clone repo
git clone https://github.com/your-org/nbtool.git /opt/nbtool
chown -R nbtool:nbtool /opt/nbtool

# Python venv
cd /opt/nbtool/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Copy and fill in env files
cp .env.example .env
# Edit .env with your secrets

# Frontend
cd /opt/nbtool/frontend
pnpm install
pnpm build

# Database
cd /opt/nbtool/backend
.venv/bin/alembic upgrade head

# Install systemd services
cp /opt/nbtool/deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now nbtool-api nbtool-frontend nbtool-worker nbtool-beat

# Caddy
cp /opt/nbtool/deploy/Caddyfile.example /etc/caddy/Caddyfile
# Edit domain name if needed
systemctl reload caddy
```

---

## Deploy Command

Run as the `nbtool` user (or via sudo):

```bash
/opt/nbtool/scripts/deploy.sh
```

This script: pulls latest git, upgrades pip deps, runs Alembic migrations, builds the frontend, restarts all four systemd services, and hits `/health` to confirm the API is up.

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `JWT_SECRET` | Random secret for session JWTs |
| `ALLOWED_EMAIL_DOMAIN` | Domain for Google OAuth restriction (e.g. `nbmediaproductions.com`) |
| `ADMIN_EMAILS` | Comma-separated admin email addresses |
| `ANTHROPIC_API_KEY` | Anthropic API key for LLM extraction |
| `NEWSAPI_KEY` | NewsAPI.org API key |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook for daily summary (optional) |
| `SENTRY_DSN` | Sentry DSN for error tracking (optional) |
| `FRONTEND_URL` | Public URL of the frontend (e.g. `https://research.nbmediaproductions.com`) |
| `ENVIRONMENT` | `production` or `development` |

Copy `frontend/.env.local.example` to `frontend/.env.local` and set `NEXT_PUBLIC_API_URL`.

---

## Backups

Automated PostgreSQL backups to Backblaze B2 run nightly via cron:

```cron
0 3 * * * nbtool /opt/nbtool/scripts/backup.sh >> /var/log/nbtool-backup.log 2>&1
```

Requires `B2_BUCKET`, `B2_KEY_ID`, `B2_APP_KEY` set in the environment (or exported from `.env`).

---

## Recall Eval

To measure pipeline recall against a curated sample:

```bash
/opt/nbtool/backend/.venv/bin/python /opt/nbtool/scripts/eval_recall.py
```

Edit `scripts/recall_sample.json` to add hand-verified sentencing cases.
