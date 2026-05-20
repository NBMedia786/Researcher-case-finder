# NB Media Sentencing Tracker — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted webapp that aggregates US homicide sentencings daily from news APIs, DOJ, and DA sites, extracts FOIA-ready fields with an LLM, deduplicates across outlets, and presents the cases in a researcher inbox for review.

**Architecture:** FastAPI backend + Celery workers + Postgres + Redis on a single VPS, fronted by a Next.js (React + Tailwind + shadcn/ui) frontend. Caddy reverse-proxies both. Google OAuth restricted to `@nbmediaproductions.com` domain. Pipeline runs every 30 min during business hours and a full sweep at 06:00 UTC.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Celery, Redis, Postgres 16, Next.js 14, React 18, Tailwind, shadcn/ui, Caddy, systemd, Anthropic Claude (Haiku 4.5).

**Spec:** See `docs/superpowers/specs/2026-05-20-nb-media-sentencing-tracker-design.md`.

---

## File Structure

```
nbtool/                              repo root (= /opt/nbtool on VPS)
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  FastAPI app entry
│   │   ├── config.py                env/settings (pydantic-settings)
│   │   ├── db.py                    SQLAlchemy engine + session
│   │   ├── models/                  ORM models (one file per table)
│   │   ├── schemas/                 Pydantic schemas for API I/O
│   │   ├── api/                     HTTP routers
│   │   ├── auth/                    Google OAuth + JWT
│   │   ├── sources/                 ingestion code (one file per source)
│   │   ├── extraction/              LLM extraction prompts + logic
│   │   ├── dedup/                   case linking / matching
│   │   ├── scoring/                 content score calculation
│   │   ├── notifications/           Slack/email summary
│   │   └── workers/                 Celery app + tasks
│   ├── alembic/                     DB migrations
│   ├── tests/                       pytest test suite
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                     Next.js App Router pages
│   │   ├── components/              React components
│   │   └── lib/                     API client, auth helpers
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── .env.local.example
├── deploy/
│   ├── systemd/                     systemd unit files
│   ├── Caddyfile.example
│   └── env.example
├── scripts/
│   ├── deploy.sh
│   ├── backup.sh
│   └── eval_recall.py
└── docs/
    └── superpowers/                 (spec + this plan)
```

**Decomposition rationale:** One file per database table, per source, per API router — keeps each unit under ~150 lines so a developer can hold it in context. Pipeline code lives in `app/sources/` (raw ingestion), `app/extraction/` (LLM), `app/dedup/` (linking) — three single-responsibility modules. Workers in `app/workers/` only orchestrate; they don't contain business logic.

---

## Phase 0 — Setup

### Task 1: Initialize repo + monorepo structure

**Files:**
- Create: `.gitignore`, `README.md`, `pyproject.toml` (root tooling)
- Create: `backend/requirements.txt`, `backend/.env.example`
- Create: `frontend/.env.local.example`

- [ ] **Step 1: Init git and create directory skeleton**

```bash
cd /path/to/nbtool
git init
mkdir -p backend/app/{models,schemas,api,auth,sources,extraction,dedup,scoring,notifications,workers}
mkdir -p backend/alembic/versions backend/tests
mkdir -p frontend/src/{app,components,lib}
mkdir -p deploy/systemd scripts
touch backend/app/__init__.py
```

- [ ] **Step 2: Create root .gitignore**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/

# Node
node_modules/
.next/
out/

# Env files
.env
.env.local
*.local

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/

# Build
dist/
build/

# Logs
*.log
```

- [ ] **Step 3: Create backend/requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
alembic==1.13.3
psycopg2-binary==2.9.9
pydantic==2.9.2
pydantic-settings==2.5.2
celery==5.4.0
redis==5.0.8
httpx==0.27.2
anthropic==0.34.2
google-auth==2.34.0
pyjwt==2.9.0
beautifulsoup4==4.12.3
feedparser==6.0.11
python-multipart==0.0.10
sentry-sdk[fastapi]==2.13.0
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-mock==3.14.0
```

- [ ] **Step 4: Create backend/.env.example**

```
# Database
DATABASE_URL=postgresql+psycopg2://nbtool:CHANGE_ME@localhost:5432/nbtool
REDIS_URL=redis://localhost:6379/0

# Auth
GOOGLE_CLIENT_ID=CHANGE_ME.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=CHANGE_ME
JWT_SECRET=CHANGE_ME_RANDOM_64_CHARS
ALLOWED_EMAIL_DOMAIN=nbmediaproductions.com
ADMIN_EMAILS=admin1@nbmediaproductions.com

# External APIs
ANTHROPIC_API_KEY=sk-ant-CHANGE_ME
NEWSAPI_KEY=CHANGE_ME
MEDIASTACK_KEY=CHANGE_ME

# App config
ENVIRONMENT=development
LOG_LEVEL=INFO
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
SENTRY_DSN=

# Notifications
SLACK_WEBHOOK_URL=
```

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "chore: initialize monorepo structure"
```

---

### Task 2: Backend scaffold — FastAPI hello world + Postgres connection

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/db.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write failing test for health endpoint**

`backend/tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pytest tests/test_health.py -v`

Expected: FAIL with "No module named 'app.main'".

- [ ] **Step 3: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://nbtool:nbtool@localhost:5432/nbtool"
    redis_url: str = "redis://localhost:6379/0"

    google_client_id: str = ""
    google_client_secret: str = ""
    jwt_secret: str = "dev-secret-change-me"
    allowed_email_domain: str = "nbmediaproductions.com"
    admin_emails: str = ""

    anthropic_api_key: str = ""
    newsapi_key: str = ""
    mediastack_key: str = ""

    environment: str = "development"
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    sentry_dsn: str = ""
    slack_webhook_url: str = ""

settings = Settings()
```

- [ ] **Step 4: Create `backend/app/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(title="NB Media Sentencing Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Create `backend/tests/conftest.py`**

```python
import os
import sys

# Make `app` importable from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 8: Set up Postgres locally**

```bash
# On the VPS (or local dev):
sudo apt install postgresql-16
sudo -u postgres psql -c "CREATE USER nbtool WITH PASSWORD 'nbtool';"
sudo -u postgres psql -c "CREATE DATABASE nbtool OWNER nbtool;"
```

- [ ] **Step 9: Commit**

```bash
git add backend/
git commit -m "feat(backend): scaffold FastAPI app with health endpoint"
```

---

### Task 3: Celery + Redis + Beat scheduler

**Files:**
- Create: `backend/app/workers/__init__.py`
- Create: `backend/app/workers/celery_app.py`
- Create: `backend/tests/test_celery_app.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_celery_app.py`:
```python
from app.workers.celery_app import celery_app

def test_celery_app_configured():
    assert celery_app.main == "nbtool"
    assert "default" in celery_app.conf.task_queues or celery_app.conf.task_default_queue == "default"

def test_celery_beat_schedule_has_pipeline():
    schedule = celery_app.conf.beat_schedule
    assert "daily_full_sweep" in schedule
    assert "light_sweep" in schedule
```

- [ ] **Step 2: Run test, confirm it fails**

Run: `pytest tests/test_celery_app.py -v`
Expected: FAIL.

- [ ] **Step 3: Create `backend/app/workers/__init__.py`** (empty file)

- [ ] **Step 4: Create `backend/app/workers/celery_app.py`**

```python
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "nbtool",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "daily_full_sweep": {
        "task": "app.workers.tasks.run_full_pipeline",
        "schedule": crontab(hour=6, minute=0),
    },
    "light_sweep": {
        "task": "app.workers.tasks.run_light_pipeline",
        "schedule": crontab(minute="*/30", hour="14-22"),
    },
}
```

- [ ] **Step 5: Create stub `backend/app/workers/tasks.py`**

```python
from app.workers.celery_app import celery_app

@celery_app.task
def run_full_pipeline():
    return "full pipeline triggered"

@celery_app.task
def run_light_pipeline():
    return "light pipeline triggered"
```

- [ ] **Step 6: Run test, verify PASS**

Run: `pytest tests/test_celery_app.py -v`

- [ ] **Step 7: Install + start Redis locally**

```bash
sudo apt install redis-server
sudo systemctl start redis-server
redis-cli ping  # should return PONG
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/workers backend/tests/test_celery_app.py
git commit -m "feat(workers): add Celery app with Beat schedule"
```

---

## Phase 1 — Database

### Task 4: All ORM models + initial Alembic migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/case.py`
- Create: `backend/app/models/article.py`
- Create: `backend/app/models/source.py`
- Create: `backend/app/models/audit_log.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_models.py`:
```python
from app.models import User, Case, Article, Source, AuditLog

def test_models_importable():
    assert User.__tablename__ == "users"
    assert Case.__tablename__ == "cases"
    assert Article.__tablename__ == "articles"
    assert Source.__tablename__ == "sources"
    assert AuditLog.__tablename__ == "audit_log"

def test_case_has_required_columns():
    cols = {c.name for c in Case.__table__.columns}
    required = {
        "id", "defendant_name", "defendant_name_normalized",
        "sentencing_date", "state", "county",
        "status", "content_score", "created_at",
    }
    assert required.issubset(cols)
```

- [ ] **Step 2: Run test, confirm it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Create `backend/app/models/user.py`**

```python
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    role = Column(Enum("admin", "researcher", name="user_role"), nullable=False, default="researcher")
    google_sub = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
```

- [ ] **Step 4: Create `backend/app/models/case.py`**

```python
import uuid
from sqlalchemy import Column, String, Integer, Date, DateTime, Enum, Text, ForeignKey, CHAR
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

CASE_STATUS = ("new", "reviewing", "approved", "rejected",
               "foia_filed", "records_received", "archived")
SENTENCE_TYPE = ("years", "life", "life_no_parole", "death")

class Case(Base):
    __tablename__ = "cases"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    defendant_name = Column(String, nullable=False)
    defendant_name_normalized = Column(String, nullable=False, index=True)
    defendant_age = Column(Integer, nullable=True)
    defendant_hometown = Column(String, nullable=True)
    victims = Column(JSONB, nullable=False, default=list)
    charges = Column(JSONB, nullable=False, default=list)
    sentence_text = Column(String, nullable=True)
    sentence_years = Column(Integer, nullable=True)
    sentence_type = Column(Enum(*SENTENCE_TYPE, name="sentence_type"), nullable=True)
    sentencing_date = Column(Date, nullable=False, index=True)
    court_name = Column(String, nullable=True)
    county = Column(String, nullable=True)
    state = Column(CHAR(2), nullable=False, index=True)
    docket_number = Column(String, nullable=True)
    judge_name = Column(String, nullable=True)
    prosecuting_office = Column(String, nullable=True)
    investigating_agency = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    content_score = Column(Integer, nullable=False, default=1)
    status = Column(Enum(*CASE_STATUS, name="case_status"), nullable=False, default="new", index=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 5: Create `backend/app/models/source.py`**

```python
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

SOURCE_TYPE = ("news_api", "rss", "scraper", "api", "webhook")

class Source(Base):
    __tablename__ = "sources"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    type = Column(Enum(*SOURCE_TYPE, name="source_type"), nullable=False)
    config = Column(JSONB, nullable=False, default=dict)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    items_fetched_24h = Column(Integer, nullable=False, default=0)
    items_extracted_24h = Column(Integer, nullable=False, default=0)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 6: Create `backend/app/models/article.py`**

```python
import uuid
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

ARTICLE_SOURCE_TYPE = ("news_api", "gdelt", "doj", "da_office", "courtlistener", "google_alert")
EXTRACTION_STATUS = ("pending", "extracted", "failed", "no_match")

class Article(Base):
    __tablename__ = "articles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=True)
    source_name = Column(String, nullable=False)
    source_type = Column(Enum(*ARTICLE_SOURCE_TYPE, name="article_source_type"), nullable=False)
    url = Column(String, unique=True, nullable=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    title = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)
    extracted_json = Column(JSONB, nullable=True)
    extraction_status = Column(Enum(*EXTRACTION_STATUS, name="extraction_status"),
                               nullable=False, default="pending", index=True)
    extraction_model = Column(String, nullable=True)
    extraction_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 7: Create `backend/app/models/audit_log.py`**

```python
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    extra = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
```

- [ ] **Step 8: Create `backend/app/models/__init__.py`**

```python
from app.models.user import User
from app.models.case import Case, CASE_STATUS, SENTENCE_TYPE
from app.models.source import Source, SOURCE_TYPE
from app.models.article import Article, ARTICLE_SOURCE_TYPE, EXTRACTION_STATUS
from app.models.audit_log import AuditLog

__all__ = [
    "User", "Case", "Source", "Article", "AuditLog",
    "CASE_STATUS", "SENTENCE_TYPE", "SOURCE_TYPE",
    "ARTICLE_SOURCE_TYPE", "EXTRACTION_STATUS",
]
```

- [ ] **Step 9: Initialize Alembic**

```bash
cd backend
alembic init alembic
```

Edit `backend/alembic.ini` — set `sqlalchemy.url = ` (blank, we'll inject from env).

- [ ] **Step 10: Edit `backend/alembic/env.py`** — set target metadata and URL from settings

Replace top of `env.py` with:
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from app.config import settings
from app.db import Base
from app.models import *  # noqa: F401,F403 — register tables

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
```

(Leave the rest of `env.py` as alembic generated it.)

- [ ] **Step 11: Generate initial migration**

```bash
cd backend
alembic revision --autogenerate -m "initial schema"
```

Inspect the generated file in `backend/alembic/versions/` to make sure all 5 tables appear.

- [ ] **Step 12: Apply migration**

```bash
alembic upgrade head
```

Verify with `psql nbtool -c "\dt"` — should list `users`, `cases`, `articles`, `sources`, `audit_log`, `alembic_version`.

- [ ] **Step 13: Run unit test, verify PASS**

```bash
pytest tests/test_models.py -v
```

- [ ] **Step 14: Add critical indexes via a follow-up migration**

```bash
alembic revision -m "add composite indexes"
```

Edit the new migration file:
```python
def upgrade():
    op.create_index(
        "ix_cases_status_sentencing_date",
        "cases", ["status", "sentencing_date"], unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        "ix_cases_dedup",
        "cases", ["defendant_name_normalized", "sentencing_date", "state"], unique=False,
    )
    op.create_index(
        "ix_cases_state_county", "cases", ["state", "county"], unique=False,
    )

def downgrade():
    op.drop_index("ix_cases_state_county", "cases")
    op.drop_index("ix_cases_dedup", "cases")
    op.drop_index("ix_cases_status_sentencing_date", "cases")
```

Run `alembic upgrade head`.

- [ ] **Step 15: Commit**

```bash
git add backend/app/models backend/alembic backend/tests/test_models.py
git commit -m "feat(db): add core models and initial migration"
```

---

## Phase 2 — Auth

### Task 5: Google OAuth token verification + domain restriction

**Files:**
- Create: `backend/app/auth/__init__.py` (empty)
- Create: `backend/app/auth/google_oauth.py`
- Create: `backend/tests/test_google_oauth.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_google_oauth.py`:
```python
import pytest
from unittest.mock import patch
from app.auth.google_oauth import verify_id_token, EmailDomainNotAllowed

VALID_PAYLOAD = {
    "sub": "google-subject-123",
    "email": "researcher@nbmediaproductions.com",
    "email_verified": True,
    "name": "A Researcher",
    "hd": "nbmediaproductions.com",
}

def test_verify_accepts_company_email():
    with patch("app.auth.google_oauth.id_token.verify_oauth2_token", return_value=VALID_PAYLOAD):
        result = verify_id_token("fake-token")
    assert result["email"] == "researcher@nbmediaproductions.com"
    assert result["google_sub"] == "google-subject-123"

def test_verify_rejects_outside_domain():
    bad = dict(VALID_PAYLOAD, email="x@gmail.com", hd=None)
    with patch("app.auth.google_oauth.id_token.verify_oauth2_token", return_value=bad):
        with pytest.raises(EmailDomainNotAllowed):
            verify_id_token("fake-token")

def test_verify_rejects_unverified_email():
    bad = dict(VALID_PAYLOAD, email_verified=False)
    with patch("app.auth.google_oauth.id_token.verify_oauth2_token", return_value=bad):
        with pytest.raises(EmailDomainNotAllowed):
            verify_id_token("fake-token")
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `pytest tests/test_google_oauth.py -v`

- [ ] **Step 3: Create `backend/app/auth/google_oauth.py`**

```python
from google.oauth2 import id_token
from google.auth.transport import requests as g_requests
from app.config import settings

class EmailDomainNotAllowed(Exception):
    pass

def verify_id_token(token: str) -> dict:
    """Verify a Google ID token and return normalized claims.

    Raises EmailDomainNotAllowed if the email doesn't end with the configured
    allowed domain, isn't verified, or is missing.
    """
    payload = id_token.verify_oauth2_token(
        token, g_requests.Request(), settings.google_client_id
    )

    email = payload.get("email", "").lower()
    if not payload.get("email_verified"):
        raise EmailDomainNotAllowed("email not verified by Google")
    if not email.endswith("@" + settings.allowed_email_domain):
        raise EmailDomainNotAllowed(
            f"email must be @{settings.allowed_email_domain}"
        )

    return {
        "google_sub": payload["sub"],
        "email": email,
        "full_name": payload.get("name"),
    }
```

- [ ] **Step 4: Run, verify PASS**

Run: `pytest tests/test_google_oauth.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth backend/tests/test_google_oauth.py
git commit -m "feat(auth): add Google ID token verification with domain restriction"
```

---

### Task 6: JWT session + login endpoint

**Files:**
- Create: `backend/app/auth/jwt_session.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py` (register router)
- Create: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_auth_api.py`:
```python
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

VERIFIED = {
    "google_sub": "g-1",
    "email": "newuser@nbmediaproductions.com",
    "full_name": "New User",
}

def test_login_creates_user_and_returns_cookie():
    with patch("app.api.auth.verify_id_token", return_value=VERIFIED):
        r = client.post("/api/auth/login", json={"id_token": "x"})
    assert r.status_code == 200
    assert "session" in r.cookies
    assert r.json()["user"]["email"] == VERIFIED["email"]

def test_login_rejects_bad_domain():
    from app.auth.google_oauth import EmailDomainNotAllowed
    with patch("app.api.auth.verify_id_token", side_effect=EmailDomainNotAllowed("bad")):
        r = client.post("/api/auth/login", json={"id_token": "x"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Create `backend/app/auth/jwt_session.py`**

```python
from datetime import datetime, timedelta, timezone
import jwt
from app.config import settings

SESSION_TTL_DAYS = 7

def create_session_token(user_id: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(days=SESSION_TTL_DAYS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def decode_session_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
```

- [ ] **Step 4: Create `backend/app/schemas/__init__.py`** (empty) and `backend/app/schemas/auth.py`

```python
from pydantic import BaseModel
from uuid import UUID

class LoginRequest(BaseModel):
    id_token: str

class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: str
    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    user: UserOut
```

- [ ] **Step 5: Create `backend/app/api/__init__.py`**

```python
from fastapi import APIRouter
from app.api import auth

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
```

- [ ] **Step 6: Create `backend/app/api/auth.py`**

```python
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.auth.google_oauth import verify_id_token, EmailDomainNotAllowed
from app.auth.jwt_session import create_session_token
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.config import settings

router = APIRouter()

def _admin_emails() -> set[str]:
    return {e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()}

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        claims = verify_id_token(body.id_token)
    except EmailDomainNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))

    user = db.query(User).filter(User.email == claims["email"]).one_or_none()
    role = "admin" if claims["email"] in _admin_emails() else "researcher"
    if user is None:
        user = User(
            email=claims["email"],
            google_sub=claims["google_sub"],
            full_name=claims["full_name"],
            role=role,
        )
        db.add(user)
    else:
        user.google_sub = claims["google_sub"]
        user.full_name = claims["full_name"] or user.full_name
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_session_token(user.id, user.email, user.role)
    response.set_cookie(
        "session", token,
        httponly=True, secure=settings.environment != "development",
        samesite="lax", max_age=7 * 24 * 3600,
    )
    return LoginResponse(user=UserOut.model_validate(user))

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}
```

- [ ] **Step 7: Modify `backend/app/main.py`** to register router

Replace existing content with:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import api_router

app = FastAPI(title="NB Media Sentencing Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Run tests, verify PASS**

Run: `pytest tests/ -v`

- [ ] **Step 9: Commit**

```bash
git add backend/app backend/tests/test_auth_api.py
git commit -m "feat(auth): add /api/auth/login with JWT session cookie"
```

---

### Task 7: Auth dependency — current_user + admin guard

**Files:**
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/tests/test_auth_deps.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_auth_deps.py`:
```python
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from app.auth.dependencies import current_user, admin_required
from app.auth.jwt_session import create_session_token

app = FastAPI()

@app.get("/me")
def me(user=Depends(current_user)):
    return {"email": user.email, "role": user.role}

@app.get("/admin")
def admin(user=Depends(admin_required)):
    return {"ok": True}

client = TestClient(app)

def test_requires_session_cookie():
    r = client.get("/me")
    assert r.status_code == 401

def test_decodes_valid_session(monkeypatch):
    from unittest.mock import MagicMock
    fake_user = MagicMock(email="r@nbmediaproductions.com", role="researcher")
    monkeypatch.setattr(
        "app.auth.dependencies._load_user",
        lambda db, user_id: fake_user,
    )
    token = create_session_token("11111111-1111-1111-1111-111111111111",
                                 "r@nbmediaproductions.com", "researcher")
    client.cookies.set("session", token)
    r = client.get("/me")
    assert r.status_code == 200
    assert r.json()["email"] == "r@nbmediaproductions.com"
    client.cookies.clear()

def test_admin_required_rejects_researcher(monkeypatch):
    from unittest.mock import MagicMock
    fake_user = MagicMock(email="r@nbmediaproductions.com", role="researcher")
    monkeypatch.setattr(
        "app.auth.dependencies._load_user",
        lambda db, user_id: fake_user,
    )
    token = create_session_token("11111111-1111-1111-1111-111111111111",
                                 "r@nbmediaproductions.com", "researcher")
    client.cookies.set("session", token)
    r = client.get("/admin")
    assert r.status_code == 403
    client.cookies.clear()
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Create `backend/app/auth/dependencies.py`**

```python
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.auth.jwt_session import decode_session_token

def _load_user(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).one_or_none()

def current_user(
    session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not session:
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        claims = decode_session_token(session)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid session")
    user = _load_user(db, claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    return user

def admin_required(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return user
```

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/dependencies.py backend/tests/test_auth_deps.py
git commit -m "feat(auth): add current_user + admin_required dependencies"
```

---

## Phase 3 — Pipeline core

### Task 8: Source base class + registry

**Files:**
- Create: `backend/app/sources/__init__.py`
- Create: `backend/app/sources/base.py`
- Create: `backend/tests/test_source_base.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_source_base.py`:
```python
from app.sources.base import IngestedArticle, BaseSource

def test_ingested_article_dataclass():
    a = IngestedArticle(
        url="https://x.com/a", title="t", published_at=None,
        raw_text="body", source_name="X", source_type="news_api",
    )
    assert a.url == "https://x.com/a"

def test_base_source_requires_fetch():
    import pytest
    class S(BaseSource):
        name = "test"
        source_type = "news_api"
    s = S(config={})
    with pytest.raises(NotImplementedError):
        list(s.fetch())
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Create `backend/app/sources/base.py`**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

@dataclass
class IngestedArticle:
    url: str
    title: str | None
    published_at: datetime | None
    raw_text: str
    source_name: str
    source_type: str

class BaseSource:
    name: str = ""
    source_type: str = ""

    def __init__(self, config: dict):
        self.config = config

    def fetch(self) -> Iterable[IngestedArticle]:
        raise NotImplementedError
```

- [ ] **Step 4: Create `backend/app/sources/__init__.py`**

```python
from app.sources.base import BaseSource, IngestedArticle

__all__ = ["BaseSource", "IngestedArticle"]
```

- [ ] **Step 5: Run tests, verify PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/app/sources backend/tests/test_source_base.py
git commit -m "feat(sources): add base source class + dataclass"
```

---

### Task 9: NewsAPI ingestion source

**Files:**
- Create: `backend/app/sources/newsapi.py`
- Create: `backend/tests/test_newsapi_source.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_newsapi_source.py`:
```python
from unittest.mock import patch, MagicMock
from app.sources.newsapi import NewsAPISource

SAMPLE_RESPONSE = {
    "status": "ok",
    "articles": [
        {
            "url": "https://example.com/article-1",
            "title": "Man sentenced to life for murder",
            "publishedAt": "2026-05-19T12:00:00Z",
            "content": "A jury sentenced John Doe to life...",
            "description": "...",
            "source": {"name": "Example News"},
        }
    ],
}

def test_fetch_returns_articles():
    src = NewsAPISource(config={"api_key": "k"})
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_RESPONSE
    with patch("app.sources.newsapi.httpx.get", return_value=mock_resp):
        out = list(src.fetch())
    assert len(out) == 1
    assert out[0].url == "https://example.com/article-1"
    assert "sentenced" in out[0].title.lower()
    assert out[0].source_type == "news_api"
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Create `backend/app/sources/newsapi.py`**

```python
from datetime import datetime, timezone, timedelta
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle

NEWSAPI_URL = "https://newsapi.org/v2/everything"

DEFAULT_QUERIES = [
    '"sentenced to life" murder',
    '"sentenced to death"',
    '"life without parole" sentenced',
    '"convicted of murder" sentenced',
    '"sentenced to" manslaughter',
]

class NewsAPISource(BaseSource):
    name = "newsapi"
    source_type = "news_api"

    def fetch(self) -> Iterable[IngestedArticle]:
        api_key = self.config.get("api_key")
        if not api_key:
            return
        queries = self.config.get("queries") or DEFAULT_QUERIES
        from_iso = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        for q in queries:
            params = {
                "q": q,
                "language": "en",
                "from": from_iso,
                "sortBy": "publishedAt",
                "pageSize": 100,
                "apiKey": api_key,
            }
            r = httpx.get(NEWSAPI_URL, params=params, timeout=30.0)
            if r.status_code != 200:
                continue
            data = r.json()
            for a in data.get("articles", []):
                pub_at = None
                if a.get("publishedAt"):
                    try:
                        pub_at = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
                    except ValueError:
                        pub_at = None
                yield IngestedArticle(
                    url=a["url"],
                    title=a.get("title"),
                    published_at=pub_at,
                    raw_text=(a.get("content") or "") + "\n\n" + (a.get("description") or ""),
                    source_name=a.get("source", {}).get("name") or "NewsAPI",
                    source_type="news_api",
                )
```

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/sources/newsapi.py backend/tests/test_newsapi_source.py
git commit -m "feat(sources): add NewsAPI ingestion source"
```

---

### Task 10: DOJ press release ingestion source

**Files:**
- Create: `backend/app/sources/doj.py`
- Create: `backend/tests/test_doj_source.py`
- Create: `backend/tests/fixtures/doj_rss.xml`

- [ ] **Step 1: Create fixture**

`backend/tests/fixtures/doj_rss.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>DOJ News</title>
  <item>
    <title>Defendant sentenced to life for first-degree murder</title>
    <link>https://www.justice.gov/news/press-release/abc-123</link>
    <pubDate>Mon, 19 May 2026 12:00:00 GMT</pubDate>
    <description>John Doe, 35, was sentenced to life in prison...</description>
  </item>
  <item>
    <title>Press release about something else entirely</title>
    <link>https://www.justice.gov/news/press-release/xyz-999</link>
    <pubDate>Mon, 19 May 2026 11:00:00 GMT</pubDate>
    <description>Indictment announced...</description>
  </item>
</channel>
</rss>
```

- [ ] **Step 2: Write failing test**

`backend/tests/test_doj_source.py`:
```python
from pathlib import Path
from unittest.mock import patch
from app.sources.doj import DOJSource

FIXTURE = (Path(__file__).parent / "fixtures" / "doj_rss.xml").read_text()

def test_filter_keeps_sentencing_items():
    src = DOJSource(config={"feeds": ["https://example/rss"]})
    with patch("app.sources.doj.httpx.get") as mget:
        mget.return_value.status_code = 200
        mget.return_value.text = FIXTURE
        out = list(src.fetch())
    urls = [a.url for a in out]
    assert "https://www.justice.gov/news/press-release/abc-123" in urls
    assert "https://www.justice.gov/news/press-release/xyz-999" not in urls
```

- [ ] **Step 3: Run, confirm FAIL**

- [ ] **Step 4: Create `backend/app/sources/doj.py`**

```python
from datetime import datetime
from typing import Iterable
from email.utils import parsedate_to_datetime
import httpx
import feedparser
from app.sources.base import BaseSource, IngestedArticle

DEFAULT_FEEDS = ["https://www.justice.gov/feeds/opa/justice-news.xml"]

SENTENCING_KEYWORDS = (
    "sentenced", "sentencing",
    "life without parole", "life in prison",
    "convicted of murder", "manslaughter",
)

def _looks_like_homicide_sentencing(title: str, description: str) -> bool:
    blob = f"{title} {description}".lower()
    has_sentence = any(k in blob for k in ("sentenced", "sentencing", "life in prison",
                                            "life without parole"))
    has_homicide = any(k in blob for k in ("murder", "homicide", "manslaughter", "killing"))
    return has_sentence and has_homicide

class DOJSource(BaseSource):
    name = "doj"
    source_type = "doj"

    def fetch(self) -> Iterable[IngestedArticle]:
        feeds = self.config.get("feeds") or DEFAULT_FEEDS
        for feed_url in feeds:
            try:
                r = httpx.get(feed_url, timeout=30.0)
                if r.status_code != 200:
                    continue
                parsed = feedparser.parse(r.text)
            except Exception:
                continue
            for entry in parsed.entries:
                title = getattr(entry, "title", "") or ""
                desc = getattr(entry, "description", "") or getattr(entry, "summary", "") or ""
                if not _looks_like_homicide_sentencing(title, desc):
                    continue
                pub = None
                if getattr(entry, "published", None):
                    try:
                        pub = parsedate_to_datetime(entry.published)
                    except Exception:
                        pub = None
                yield IngestedArticle(
                    url=entry.link,
                    title=title,
                    published_at=pub,
                    raw_text=desc,
                    source_name="DOJ",
                    source_type="doj",
                )
```

- [ ] **Step 5: Run tests, verify PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/app/sources/doj.py backend/tests/test_doj_source.py backend/tests/fixtures
git commit -m "feat(sources): add DOJ RSS ingestion source"
```

---

### Task 11: LLM extraction with Claude Haiku

**Files:**
- Create: `backend/app/extraction/__init__.py` (empty)
- Create: `backend/app/extraction/prompts.py`
- Create: `backend/app/extraction/extractor.py`
- Create: `backend/tests/test_extractor.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_extractor.py`:
```python
import json
from unittest.mock import patch, MagicMock
from app.extraction.extractor import extract_case_fields, EXTRACTION_MODEL

SAMPLE_TEXT = """John Doe, 34, of Houston, was sentenced Monday to life
without parole after being convicted of first-degree murder
in the 2024 killing of his neighbor Maria Lopez, 28.
Judge Jane Smith of the Harris County Criminal District Court
imposed the sentence. The Houston Police Department investigated."""

VALID_LLM_JSON = {
    "is_homicide_sentencing": True,
    "defendant_name": "John Doe",
    "defendant_age": 34,
    "defendant_hometown": "Houston, TX",
    "victims": [{"name": "Maria Lopez", "age": 28}],
    "charges": [{"statute": None, "degree": "first-degree", "description": "first-degree murder"}],
    "sentence_text": "life without parole",
    "sentence_type": "life_no_parole",
    "sentence_years": None,
    "sentencing_date": "2026-05-19",
    "court_name": "Harris County Criminal District Court",
    "county": "Harris",
    "state": "TX",
    "docket_number": None,
    "judge_name": "Jane Smith",
    "prosecuting_office": None,
    "investigating_agency": "Houston Police Department",
    "summary": "John Doe sentenced to life without parole for first-degree murder of Maria Lopez.",
}

def test_extract_returns_structured_fields():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(VALID_LLM_JSON))]
    with patch("app.extraction.extractor.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.return_value = mock_msg
        result = extract_case_fields(SAMPLE_TEXT, source_name="Local News")
    assert result["status"] == "extracted"
    assert result["data"]["defendant_name"] == "John Doe"
    assert result["data"]["state"] == "TX"
    assert result["model"] == EXTRACTION_MODEL

def test_extract_marks_no_match_when_not_homicide_sentencing():
    bad = dict(VALID_LLM_JSON, is_homicide_sentencing=False)
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(bad))]
    with patch("app.extraction.extractor.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.return_value = mock_msg
        result = extract_case_fields("unrelated text", source_name="X")
    assert result["status"] == "no_match"
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Create `backend/app/extraction/prompts.py`**

```python
EXTRACTION_PROMPT_VERSION = "v1"

EXTRACTION_SYSTEM_PROMPT = """You extract structured facts about US homicide
sentencings from news articles. You ALWAYS reply with a single JSON object,
no markdown, no commentary.

Schema:
{
  "is_homicide_sentencing": bool,   // true only if a US criminal court has
                                    // just sentenced someone for murder,
                                    // homicide, or manslaughter
  "defendant_name": string|null,
  "defendant_age": int|null,
  "defendant_hometown": string|null,
  "victims": [{"name": string|null, "age": int|null}],
  "charges": [{"statute": string|null, "degree": string|null,
               "description": string}],
  "sentence_text": string|null,     // verbatim sentence phrase
  "sentence_type": "years"|"life"|"life_no_parole"|"death"|null,
  "sentence_years": int|null,       // numeric only, null if life/death
  "sentencing_date": "YYYY-MM-DD"|null,  // date of sentencing
  "court_name": string|null,
  "county": string|null,            // county name without 'County' suffix
  "state": string|null,             // 2-letter US state code
  "docket_number": string|null,
  "judge_name": string|null,
  "prosecuting_office": string|null,
  "investigating_agency": string|null,
  "summary": string                  // one-paragraph plain-English summary
}

Set is_homicide_sentencing=false if:
- the article is about an arrest, charge, conviction without sentencing
- the case is not a US case
- the case is not homicide/murder/manslaughter
- the article is opinion/analysis, not a news report of sentencing
"""

def build_user_prompt(article_text: str, source_name: str) -> str:
    return f"""Source: {source_name}

Article:
{article_text[:8000]}

Extract the schema above as a single JSON object."""
```

- [ ] **Step 4: Create `backend/app/extraction/extractor.py`**

```python
import json
from anthropic import Anthropic
from app.config import settings
from app.extraction.prompts import (
    EXTRACTION_SYSTEM_PROMPT, EXTRACTION_PROMPT_VERSION, build_user_prompt,
)

EXTRACTION_MODEL = "claude-haiku-4-5-20251001"

REQUIRED_KEYS = {
    "is_homicide_sentencing", "defendant_name", "victims", "charges",
    "sentence_type", "sentencing_date", "state", "summary",
}

def extract_case_fields(article_text: str, source_name: str) -> dict:
    """Run LLM extraction. Returns dict with keys: status, data, model, prompt_version, error."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    try:
        msg = client.messages.create(
            model=EXTRACTION_MODEL,
            max_tokens=2000,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(article_text, source_name)}],
        )
        text = msg.content[0].text.strip()
        # The model is instructed to output pure JSON, but be defensive:
        if text.startswith("```"):
            text = text.strip("` \n")
            if text.startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return {"status": "failed", "error": f"json_decode: {e}",
                "model": EXTRACTION_MODEL, "prompt_version": EXTRACTION_PROMPT_VERSION}
    except Exception as e:
        return {"status": "failed", "error": f"llm_error: {e}",
                "model": EXTRACTION_MODEL, "prompt_version": EXTRACTION_PROMPT_VERSION}

    if not REQUIRED_KEYS.issubset(set(data.keys())):
        return {"status": "failed", "error": "missing required keys",
                "data": data, "model": EXTRACTION_MODEL,
                "prompt_version": EXTRACTION_PROMPT_VERSION}

    if not data.get("is_homicide_sentencing"):
        return {"status": "no_match", "data": data, "model": EXTRACTION_MODEL,
                "prompt_version": EXTRACTION_PROMPT_VERSION}

    return {"status": "extracted", "data": data, "model": EXTRACTION_MODEL,
            "prompt_version": EXTRACTION_PROMPT_VERSION}
```

- [ ] **Step 5: Run tests, verify PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/app/extraction backend/tests/test_extractor.py
git commit -m "feat(extraction): add Claude-Haiku-based field extractor"
```

---

### Task 12: Dedup + case linking

**Files:**
- Create: `backend/app/dedup/__init__.py` (empty)
- Create: `backend/app/dedup/matcher.py`
- Create: `backend/tests/test_dedup.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_dedup.py`:
```python
from app.dedup.matcher import normalize_name

def test_normalize_strips_punctuation():
    assert normalize_name("John Q. Doe Jr.") == "john q doe jr"

def test_normalize_collapses_whitespace():
    assert normalize_name("  John   Doe  ") == "john doe"

def test_normalize_handles_unicode():
    assert normalize_name("José García") == "jose garcia"
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Create `backend/app/dedup/matcher.py`**

```python
import re
import unicodedata
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models import Case

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

def normalize_name(name: str) -> str:
    if not name:
        return ""
    # NFKD then strip combining marks to fold accents
    nfkd = unicodedata.normalize("NFKD", name)
    no_accent = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = no_accent.lower()
    no_punct = _PUNCT_RE.sub("", lowered)
    return _WS_RE.sub(" ", no_punct).strip()

def find_matching_case(
    db: Session,
    defendant_name: str,
    sentencing_date: date,
    state: str,
    window_days: int = 3,
) -> Case | None:
    """Return existing case if defendant + date(±window) + state match. Else None."""
    if not defendant_name or not sentencing_date or not state:
        return None
    nname = normalize_name(defendant_name)
    if not nname:
        return None
    lo = sentencing_date - timedelta(days=window_days)
    hi = sentencing_date + timedelta(days=window_days)
    return (
        db.query(Case)
        .filter(Case.defendant_name_normalized == nname)
        .filter(Case.state == state.upper())
        .filter(Case.sentencing_date.between(lo, hi))
        .first()
    )

def merge_extracted_into_case(case: Case, extracted: dict) -> None:
    """Fill empty fields on `case` with values from `extracted`. Never overwrite."""
    fillable = (
        "defendant_age", "defendant_hometown", "sentence_text", "sentence_years",
        "sentence_type", "court_name", "county", "docket_number", "judge_name",
        "prosecuting_office", "investigating_agency", "summary",
    )
    for f in fillable:
        if getattr(case, f, None) in (None, "", 0) and extracted.get(f):
            setattr(case, f, extracted[f])
```

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Add an integration test that exercises `find_matching_case`**

`backend/tests/test_dedup_integration.py`:
```python
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import Case
from app.dedup.matcher import find_matching_case, normalize_name

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()

def test_find_matching_case_exact(db):
    c = Case(
        defendant_name="John Doe",
        defendant_name_normalized=normalize_name("John Doe"),
        sentencing_date=date(2026, 5, 19),
        state="TX",
    )
    db.add(c); db.commit()
    m = find_matching_case(db, "JOHN  DOE", date(2026, 5, 20), "TX")
    assert m is not None and m.id == c.id

def test_find_matching_case_outside_window_returns_none(db):
    c = Case(
        defendant_name="John Doe",
        defendant_name_normalized=normalize_name("John Doe"),
        sentencing_date=date(2026, 5, 1),
        state="TX",
    )
    db.add(c); db.commit()
    m = find_matching_case(db, "John Doe", date(2026, 5, 20), "TX")
    assert m is None
```

Note: SQLite doesn't support all Postgres types — for this test, use sqlite-friendly model fixtures or skip JSONB columns. If the `Case` model rejects sqlite, mark this test as `@pytest.mark.postgres` and skip in CI without Postgres. Alternative: spin up a test Postgres via Docker for CI.

- [ ] **Step 6: Run tests, verify PASS (or properly skipped)**

- [ ] **Step 7: Commit**

```bash
git add backend/app/dedup backend/tests/test_dedup.py backend/tests/test_dedup_integration.py
git commit -m "feat(dedup): add normalization + case-matching"
```

---

### Task 13: Pipeline orchestrator + Celery wiring

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Create: `backend/app/workers/pipeline.py`
- Create: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_pipeline.py`:
```python
from datetime import date
from unittest.mock import patch, MagicMock
from app.workers.pipeline import process_article
from app.sources.base import IngestedArticle

ARTICLE = IngestedArticle(
    url="https://example.com/a", title="Sentenced", published_at=None,
    raw_text="John Doe sentenced to life...", source_name="Ex", source_type="news_api",
)

EXTRACTED = {
    "status": "extracted",
    "model": "claude-haiku-4-5",
    "prompt_version": "v1",
    "data": {
        "is_homicide_sentencing": True,
        "defendant_name": "John Doe",
        "defendant_age": 34,
        "defendant_hometown": "Houston, TX",
        "victims": [], "charges": [],
        "sentence_text": "life", "sentence_type": "life",
        "sentence_years": None, "sentencing_date": "2026-05-19",
        "court_name": None, "county": "Harris", "state": "TX",
        "docket_number": None, "judge_name": None,
        "prosecuting_office": None, "investigating_agency": None,
        "summary": "summary",
    },
}

def test_process_article_creates_case_and_article(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with patch("app.workers.pipeline.extract_case_fields", return_value=EXTRACTED), \
         patch("app.workers.pipeline.find_matching_case", return_value=None):
        out = process_article(db, ARTICLE)
    assert out["created_case"] is True
    db.add.assert_called()
    db.commit.assert_called()
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Create `backend/app/workers/pipeline.py`**

```python
from datetime import date as date_cls, datetime
from sqlalchemy.orm import Session
from app.models import Article, Case
from app.sources.base import IngestedArticle
from app.extraction.extractor import extract_case_fields
from app.dedup.matcher import find_matching_case, normalize_name, merge_extracted_into_case

def _parse_date(s: str | None) -> date_cls | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None

def process_article(db: Session, ia: IngestedArticle) -> dict:
    """Idempotent: same URL twice = no-op on second call."""
    existing = db.query(Article).filter(Article.url == ia.url).one_or_none()
    if existing and existing.extraction_status in ("extracted", "no_match"):
        return {"skipped": True, "reason": "already processed"}

    article = existing or Article(
        url=ia.url, title=ia.title, published_at=ia.published_at,
        raw_text=ia.raw_text, source_name=ia.source_name,
        source_type=ia.source_type, extraction_status="pending",
    )
    if not existing:
        db.add(article)
        db.flush()  # so article.id exists

    result = extract_case_fields(ia.raw_text, ia.source_name)
    article.extracted_json = result.get("data")
    article.extraction_model = result.get("model")
    article.extraction_error = result.get("error")

    if result["status"] != "extracted":
        article.extraction_status = result["status"]
        db.commit()
        return {"skipped": True, "reason": result["status"]}

    data = result["data"]
    sentencing_date = _parse_date(data.get("sentencing_date"))
    state = (data.get("state") or "").upper()[:2]
    defendant = data.get("defendant_name") or ""

    if not (sentencing_date and state and defendant):
        article.extraction_status = "no_match"
        db.commit()
        return {"skipped": True, "reason": "missing key fields"}

    match = find_matching_case(db, defendant, sentencing_date, state)
    created = False
    if match is None:
        case = Case(
            defendant_name=defendant,
            defendant_name_normalized=normalize_name(defendant),
            defendant_age=data.get("defendant_age"),
            defendant_hometown=data.get("defendant_hometown"),
            victims=data.get("victims") or [],
            charges=data.get("charges") or [],
            sentence_text=data.get("sentence_text"),
            sentence_years=data.get("sentence_years"),
            sentence_type=data.get("sentence_type"),
            sentencing_date=sentencing_date,
            court_name=data.get("court_name"),
            county=data.get("county"),
            state=state,
            docket_number=data.get("docket_number"),
            judge_name=data.get("judge_name"),
            prosecuting_office=data.get("prosecuting_office"),
            investigating_agency=data.get("investigating_agency"),
            summary=data.get("summary"),
            status="new",
        )
        db.add(case)
        db.flush()
        created = True
    else:
        case = match
        merge_extracted_into_case(case, data)

    article.case_id = case.id
    article.extraction_status = "extracted"
    db.commit()
    return {"created_case": created, "case_id": str(case.id)}
```

- [ ] **Step 4: Wire it into Celery tasks**

Replace `backend/app/workers/tasks.py` with:
```python
from datetime import datetime, timezone
from app.workers.celery_app import celery_app
from app.workers.pipeline import process_article
from app.db import SessionLocal
from app.models import Source
from app.sources.newsapi import NewsAPISource
from app.sources.doj import DOJSource
from app.config import settings

SOURCE_REGISTRY = {
    "newsapi": NewsAPISource,
    "doj": DOJSource,
}

def _build_source(row: Source):
    cls = SOURCE_REGISTRY.get(row.name)
    if cls is None:
        return None
    cfg = dict(row.config or {})
    # Inject API keys from settings
    if row.name == "newsapi":
        cfg["api_key"] = cfg.get("api_key") or settings.newsapi_key
    return cls(config=cfg)

@celery_app.task(bind=True, max_retries=3)
def ingest_source(self, source_id: str):
    db = SessionLocal()
    try:
        row = db.query(Source).filter(Source.id == source_id, Source.is_active).one_or_none()
        if row is None:
            return {"skipped": True}
        src = _build_source(row)
        if src is None:
            return {"skipped": True, "reason": "no handler"}
        fetched, extracted = 0, 0
        for ia in src.fetch():
            fetched += 1
            try:
                process_article(db, ia)
                extracted += 1
            except Exception:
                db.rollback()
                continue
        row.items_fetched_24h = fetched
        row.items_extracted_24h = extracted
        row.last_run_at = datetime.now(timezone.utc)
        row.last_success_at = datetime.now(timezone.utc)
        row.consecutive_failures = 0
        db.commit()
        return {"fetched": fetched, "extracted": extracted}
    except Exception as e:
        try:
            row = db.query(Source).filter(Source.id == source_id).one_or_none()
            if row:
                row.consecutive_failures = (row.consecutive_failures or 0) + 1
                row.last_run_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.rollback()
        raise self.retry(exc=e, countdown=60) from e
    finally:
        db.close()

@celery_app.task
def run_full_pipeline():
    db = SessionLocal()
    try:
        ids = [str(s.id) for s in db.query(Source).filter(Source.is_active).all()]
    finally:
        db.close()
    for sid in ids:
        ingest_source.delay(sid)
    return {"dispatched": len(ids)}

@celery_app.task
def run_light_pipeline():
    return run_full_pipeline()
```

- [ ] **Step 5: Seed two source rows via Alembic data migration**

```bash
cd backend
alembic revision -m "seed initial sources"
```

Edit the new migration:
```python
import uuid
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.execute(sa.text("""
        INSERT INTO sources (id, name, type, config, is_active,
                             items_fetched_24h, items_extracted_24h,
                             consecutive_failures)
        VALUES
        (gen_random_uuid(), 'newsapi', 'news_api', '{}'::jsonb, true, 0, 0, 0),
        (gen_random_uuid(), 'doj', 'rss', '{}'::jsonb, true, 0, 0, 0)
    """))

def downgrade():
    op.execute("DELETE FROM sources WHERE name IN ('newsapi', 'doj')")
```

(`gen_random_uuid()` requires the `pgcrypto` extension. If not enabled: prepend `CREATE EXTENSION IF NOT EXISTS pgcrypto;` to the upgrade.)

Run: `alembic upgrade head`.

- [ ] **Step 6: Run tests, verify PASS**

- [ ] **Step 7: Manual smoke test (optional with real keys)**

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info &
celery -A app.workers.celery_app beat --loglevel=info &
python -c "from app.workers.tasks import run_full_pipeline; print(run_full_pipeline.delay().get(timeout=120))"
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/workers backend/tests/test_pipeline.py backend/alembic/versions
git commit -m "feat(pipeline): orchestrator + Celery tasks + initial source seed"
```

---

## Phase 4 — Backend API

### Task 14: Cases list endpoint (inbox)

**Files:**
- Create: `backend/app/schemas/case.py`
- Create: `backend/app/api/cases.py`
- Modify: `backend/app/api/__init__.py` (register router)
- Create: `backend/tests/test_cases_api.py`

- [ ] **Step 1: Create `backend/app/schemas/case.py`**

```python
from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class CaseListItem(BaseModel):
    id: UUID
    defendant_name: str
    defendant_age: Optional[int]
    defendant_hometown: Optional[str]
    sentencing_date: date
    state: str
    county: Optional[str]
    sentence_text: Optional[str]
    sentence_type: Optional[str]
    content_score: int
    status: str
    summary: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True

class CaseListResponse(BaseModel):
    items: list[CaseListItem]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 2: Write failing test**

`backend/tests/test_cases_api.py`:
```python
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Case
from app.dedup.matcher import normalize_name

client = TestClient(app)

# Pre-issue a session cookie that points to a real user — see test_auth_deps for pattern.
# For brevity we monkeypatch current_user via dependency_overrides:
from app.auth.dependencies import current_user
from unittest.mock import MagicMock

app.dependency_overrides[current_user] = lambda: MagicMock(
    id="00000000-0000-0000-0000-000000000001",
    email="r@nbmediaproductions.com", role="researcher")

def _make_case(db, **kw):
    c = Case(
        defendant_name=kw["name"],
        defendant_name_normalized=normalize_name(kw["name"]),
        sentencing_date=kw.get("d", date(2026, 5, 19)),
        state=kw.get("state", "TX"),
        status=kw.get("status", "new"),
        content_score=kw.get("score", 3),
    )
    db.add(c); db.commit(); return c

def test_list_returns_new_cases(db_session):
    _make_case(db_session, name="John Doe")
    _make_case(db_session, name="Jane Roe")
    r = client.get("/api/cases?status=new")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert all(i["status"] == "new" for i in body["items"])
```

Add a `db_session` fixture to `conftest.py` that wraps each test in a transaction and rolls back:

```python
import pytest
from app.db import SessionLocal, engine, Base

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    yield

@pytest.fixture
def db_session():
    db = SessionLocal()
    db.begin_nested()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
```

(For real test isolation, prefer a separate test database or transactional rollback.)

- [ ] **Step 3: Run, confirm FAIL**

- [ ] **Step 4: Create `backend/app/api/cases.py`**

```python
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db import get_db
from app.models import Case
from app.auth.dependencies import current_user
from app.schemas.case import CaseListResponse, CaseListItem

router = APIRouter()

@router.get("", response_model=CaseListResponse)
def list_cases(
    db: Session = Depends(get_db),
    user=Depends(current_user),
    status: Optional[str] = None,
    state: Optional[str] = None,
    min_score: Optional[int] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    qry = db.query(Case)
    if status:
        qry = qry.filter(Case.status == status)
    if state:
        qry = qry.filter(Case.state == state.upper())
    if min_score:
        qry = qry.filter(Case.content_score >= min_score)
    if q:
        like = f"%{q.lower()}%"
        qry = qry.filter(or_(
            Case.defendant_name.ilike(like),
            Case.summary.ilike(like),
        ))
    total = qry.count()
    items = (qry
             .order_by(Case.content_score.desc(), Case.sentencing_date.desc())
             .offset((page - 1) * page_size)
             .limit(page_size)
             .all())
    return CaseListResponse(
        items=[CaseListItem.model_validate(c) for c in items],
        total=total, page=page, page_size=page_size,
    )
```

- [ ] **Step 5: Register router in `backend/app/api/__init__.py`**

```python
from fastapi import APIRouter
from app.api import auth, cases

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
```

- [ ] **Step 6: Run tests, verify PASS**

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/cases.py backend/app/api/__init__.py backend/app/schemas/case.py backend/tests/test_cases_api.py backend/tests/conftest.py
git commit -m "feat(api): GET /api/cases with filters + pagination"
```

---

### Task 15: Case detail + update endpoint

**Files:**
- Modify: `backend/app/schemas/case.py` (add detail + update)
- Modify: `backend/app/api/cases.py`
- Create: `backend/tests/test_case_detail.py`

- [ ] **Step 1: Extend schemas in `backend/app/schemas/case.py`**

Add to the file:
```python
from datetime import date as _date  # if not imported

class CaseArticle(BaseModel):
    id: UUID
    url: str
    title: Optional[str]
    source_name: str
    source_type: str
    published_at: Optional[datetime]
    class Config:
        from_attributes = True

class CaseDetail(CaseListItem):
    victims: list
    charges: list
    docket_number: Optional[str]
    judge_name: Optional[str]
    court_name: Optional[str]
    prosecuting_office: Optional[str]
    investigating_agency: Optional[str]
    sentence_years: Optional[int]
    notes: Optional[str]
    articles: list[CaseArticle]

class CaseUpdate(BaseModel):
    defendant_name: Optional[str] = None
    defendant_age: Optional[int] = None
    defendant_hometown: Optional[str] = None
    court_name: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    docket_number: Optional[str] = None
    judge_name: Optional[str] = None
    prosecuting_office: Optional[str] = None
    investigating_agency: Optional[str] = None
    notes: Optional[str] = None
```

- [ ] **Step 2: Write failing test**

`backend/tests/test_case_detail.py`:
```python
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.models import Case
from app.dedup.matcher import normalize_name

client = TestClient(app)

def test_case_detail_returns_full_record(db_session):
    c = Case(
        defendant_name="X Y",
        defendant_name_normalized=normalize_name("X Y"),
        sentencing_date=date(2026, 5, 19),
        state="TX", status="new", content_score=2,
    )
    db_session.add(c); db_session.commit()
    r = client.get(f"/api/cases/{c.id}")
    assert r.status_code == 200
    assert r.json()["defendant_name"] == "X Y"

def test_case_update_modifies_fields(db_session):
    c = Case(
        defendant_name="A B",
        defendant_name_normalized=normalize_name("A B"),
        sentencing_date=date(2026, 5, 19),
        state="TX", status="new", content_score=2,
    )
    db_session.add(c); db_session.commit()
    r = client.patch(f"/api/cases/{c.id}", json={"county": "Harris", "notes": "looks good"})
    assert r.status_code == 200
    db_session.refresh(c)
    assert c.county == "Harris"
    assert c.notes == "looks good"
```

- [ ] **Step 3: Run, confirm FAIL**

- [ ] **Step 4: Add detail + update routes to `backend/app/api/cases.py`**

Append:
```python
from fastapi import HTTPException
from uuid import UUID as UUID_T
from app.models import Article
from app.schemas.case import CaseDetail, CaseArticle, CaseUpdate

@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: UUID_T, db: Session = Depends(get_db), user=Depends(current_user)):
    c = db.query(Case).filter(Case.id == case_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="case not found")
    arts = db.query(Article).filter(Article.case_id == case_id).all()
    base = CaseListItem.model_validate(c).model_dump()
    return CaseDetail(
        **base,
        victims=c.victims or [],
        charges=c.charges or [],
        docket_number=c.docket_number,
        judge_name=c.judge_name,
        court_name=c.court_name,
        prosecuting_office=c.prosecuting_office,
        investigating_agency=c.investigating_agency,
        sentence_years=c.sentence_years,
        notes=c.notes,
        articles=[CaseArticle.model_validate(a) for a in arts],
    )

@router.patch("/{case_id}", response_model=CaseDetail)
def update_case(case_id: UUID_T, body: CaseUpdate,
                db: Session = Depends(get_db), user=Depends(current_user)):
    c = db.query(Case).filter(Case.id == case_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="case not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "state" and value:
            value = value.upper()[:2]
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return get_case(case_id, db, user)
```

- [ ] **Step 5: Run tests, verify PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/cases.py backend/app/schemas/case.py backend/tests/test_case_detail.py
git commit -m "feat(api): case detail + PATCH update"
```

---

### Task 16: Case status transitions (approve/reject/foia_filed)

**Files:**
- Modify: `backend/app/api/cases.py`
- Create: `backend/tests/test_case_status.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.models import Case
from app.dedup.matcher import normalize_name

client = TestClient(app)

def _case(db, status="new"):
    c = Case(
        defendant_name="X Y",
        defendant_name_normalized=normalize_name("X Y"),
        sentencing_date=date(2026, 5, 19),
        state="TX", status=status, content_score=2,
    )
    db.add(c); db.commit(); return c

def test_approve_transitions(db_session):
    c = _case(db_session)
    r = client.post(f"/api/cases/{c.id}/transition", json={"action": "approve"})
    assert r.status_code == 200
    db_session.refresh(c)
    assert c.status == "approved"

def test_reject_transitions(db_session):
    c = _case(db_session)
    r = client.post(f"/api/cases/{c.id}/transition", json={"action": "reject"})
    db_session.refresh(c)
    assert c.status == "rejected"

def test_invalid_action_rejected(db_session):
    c = _case(db_session)
    r = client.post(f"/api/cases/{c.id}/transition", json={"action": "nonsense"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Add transition route to `backend/app/api/cases.py`**

```python
from datetime import datetime, timezone
from pydantic import BaseModel as _BM
from app.models import AuditLog

class TransitionRequest(_BM):
    action: str
    note: str | None = None

ACTION_MAP = {
    "approve": "approved",
    "reject": "rejected",
    "needs_info": "reviewing",
    "mark_foia_filed": "foia_filed",
    "mark_records_received": "records_received",
    "archive": "archived",
}

@router.post("/{case_id}/transition", response_model=CaseDetail)
def transition_case(case_id: UUID_T, body: TransitionRequest,
                    db: Session = Depends(get_db), user=Depends(current_user)):
    new_status = ACTION_MAP.get(body.action)
    if new_status is None:
        raise HTTPException(status_code=400, detail="invalid action")
    c = db.query(Case).filter(Case.id == case_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="case not found")
    c.status = new_status
    c.reviewed_by = user.id
    c.reviewed_at = datetime.now(timezone.utc)
    if body.note:
        c.notes = (c.notes + "\n" if c.notes else "") + body.note
    db.add(AuditLog(
        user_id=user.id, action=f"case_{body.action}",
        entity_type="case", entity_id=case_id,
        extra={"new_status": new_status, "note": body.note},
    ))
    db.commit()
    db.refresh(c)
    return get_case(case_id, db, user)
```

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/cases.py backend/tests/test_case_status.py
git commit -m "feat(api): case status transitions with audit log"
```

---

### Task 17: Sources management endpoints (admin)

**Files:**
- Create: `backend/app/schemas/source.py`
- Create: `backend/app/api/sources.py`
- Modify: `backend/app/api/__init__.py`
- Create: `backend/tests/test_sources_api.py`

- [ ] **Step 1: Create `backend/app/schemas/source.py`**

```python
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class SourceItem(BaseModel):
    id: UUID
    name: str
    type: str
    is_active: bool
    last_run_at: Optional[datetime]
    last_success_at: Optional[datetime]
    items_fetched_24h: int
    items_extracted_24h: int
    consecutive_failures: int
    class Config:
        from_attributes = True

class SourceList(BaseModel):
    items: list[SourceItem]

class SourceToggle(BaseModel):
    is_active: bool
```

- [ ] **Step 2: Write failing test**

`backend/tests/test_sources_api.py`:
```python
from fastapi.testclient import TestClient
from app.main import app
from app.models import Source
from app.auth.dependencies import current_user, admin_required
from unittest.mock import MagicMock

app.dependency_overrides[admin_required] = lambda: MagicMock(
    id="00000000-0000-0000-0000-000000000001",
    email="a@nbmediaproductions.com", role="admin")

client = TestClient(app)

def test_list_sources(db_session):
    db_session.add(Source(name="x", type="api", is_active=True, config={},
                          items_fetched_24h=0, items_extracted_24h=0,
                          consecutive_failures=0))
    db_session.commit()
    r = client.get("/api/sources")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["items"]]
    assert "x" in names

def test_toggle_source(db_session):
    s = Source(name="y", type="api", is_active=True, config={},
               items_fetched_24h=0, items_extracted_24h=0, consecutive_failures=0)
    db_session.add(s); db_session.commit()
    r = client.patch(f"/api/sources/{s.id}", json={"is_active": False})
    assert r.status_code == 200
    db_session.refresh(s)
    assert s.is_active is False
```

- [ ] **Step 3: Run, confirm FAIL**

- [ ] **Step 4: Create `backend/app/api/sources.py`**

```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Source
from app.auth.dependencies import admin_required
from app.schemas.source import SourceList, SourceItem, SourceToggle

router = APIRouter()

@router.get("", response_model=SourceList)
def list_sources(db: Session = Depends(get_db), admin=Depends(admin_required)):
    rows = db.query(Source).order_by(Source.name).all()
    return SourceList(items=[SourceItem.model_validate(r) for r in rows])

@router.patch("/{source_id}", response_model=SourceItem)
def toggle_source(source_id: UUID, body: SourceToggle,
                  db: Session = Depends(get_db), admin=Depends(admin_required)):
    s = db.query(Source).filter(Source.id == source_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="source not found")
    s.is_active = body.is_active
    db.commit()
    db.refresh(s)
    return SourceItem.model_validate(s)

@router.post("/{source_id}/run")
def trigger_source(source_id: UUID, db: Session = Depends(get_db),
                   admin=Depends(admin_required)):
    s = db.query(Source).filter(Source.id == source_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="source not found")
    from app.workers.tasks import ingest_source
    ingest_source.delay(str(s.id))
    return {"queued": True}
```

- [ ] **Step 5: Register in `backend/app/api/__init__.py`**

```python
from app.api import auth, cases, sources

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
```

- [ ] **Step 6: Run tests, verify PASS**

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/sources.py backend/app/api/__init__.py backend/app/schemas/source.py backend/tests/test_sources_api.py
git commit -m "feat(api): sources list/toggle/run-now (admin)"
```

---

### Task 18: Users management endpoints (admin)

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/api/users.py`
- Modify: `backend/app/api/__init__.py`
- Create: `backend/tests/test_users_api.py`

- [ ] **Step 1: Create `backend/app/schemas/user.py`**

```python
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class UserItem(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    last_login_at: Optional[datetime]
    class Config:
        from_attributes = True

class UserList(BaseModel):
    items: list[UserItem]

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
```

- [ ] **Step 2: Write failing test**

`backend/tests/test_users_api.py`:
```python
from fastapi.testclient import TestClient
from app.main import app
from app.models import User
from app.auth.dependencies import admin_required
from unittest.mock import MagicMock

app.dependency_overrides[admin_required] = lambda: MagicMock(
    id="00000000-0000-0000-0000-000000000001",
    email="a@nbmediaproductions.com", role="admin")

client = TestClient(app)

def test_list_users(db_session):
    db_session.add(User(email="x@nbmediaproductions.com", role="researcher", is_active=True))
    db_session.commit()
    r = client.get("/api/users")
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()["items"]]
    assert "x@nbmediaproductions.com" in emails

def test_promote_user(db_session):
    u = User(email="y@nbmediaproductions.com", role="researcher", is_active=True)
    db_session.add(u); db_session.commit()
    r = client.patch(f"/api/users/{u.id}", json={"role": "admin"})
    assert r.status_code == 200
    db_session.refresh(u)
    assert u.role == "admin"
```

- [ ] **Step 3: Run, confirm FAIL**

- [ ] **Step 4: Create `backend/app/api/users.py`**

```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.auth.dependencies import admin_required
from app.schemas.user import UserList, UserItem, UserUpdate

router = APIRouter()

VALID_ROLES = {"admin", "researcher"}

@router.get("", response_model=UserList)
def list_users(db: Session = Depends(get_db), admin=Depends(admin_required)):
    rows = db.query(User).order_by(User.created_at.desc()).all()
    return UserList(items=[UserItem.model_validate(u) for u in rows])

@router.patch("/{user_id}", response_model=UserItem)
def update_user(user_id: UUID, body: UserUpdate,
                db: Session = Depends(get_db), admin=Depends(admin_required)):
    u = db.query(User).filter(User.id == user_id).one_or_none()
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")
    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="invalid role")
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    db.commit()
    db.refresh(u)
    return UserItem.model_validate(u)
```

- [ ] **Step 5: Register in `backend/app/api/__init__.py`**

```python
from app.api import auth, cases, sources, users

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
```

- [ ] **Step 6: Add a `GET /api/me` endpoint in `app/api/auth.py`**

```python
from app.auth.dependencies import current_user

@router.get("/me", response_model=UserOut)
def me(user=Depends(current_user)):
    return UserOut.model_validate(user)
```

- [ ] **Step 7: Run tests, verify PASS**

- [ ] **Step 8: Commit**

```bash
git add backend/app
git commit -m "feat(api): users list/update + /api/auth/me"
```

---

## Phase 5 — Frontend

### Task 19: Next.js scaffold + Tailwind + shadcn/ui

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/.env.local.example`

- [ ] **Step 1: Initialize Next.js**

```bash
cd frontend
npx create-next-app@14 . \
  --typescript --tailwind --eslint --app \
  --src-dir --import-alias "@/*" \
  --no-experimental-app
```

(Accept defaults for prompts not in the flags.)

- [ ] **Step 2: Install shadcn/ui**

```bash
npx shadcn-ui@latest init
```

Choose defaults: New York style, Slate color, CSS variables yes.

- [ ] **Step 3: Install the base shadcn components we'll use**

```bash
npx shadcn-ui@latest add button card input textarea select badge dialog table tabs toast tooltip dropdown-menu
```

- [ ] **Step 4: Create `frontend/.env.local.example`**

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GOOGLE_CLIENT_ID=CHANGE_ME.apps.googleusercontent.com
```

- [ ] **Step 5: Replace `frontend/src/app/page.tsx` with a redirect**

```tsx
import { redirect } from "next/navigation";
export default function Home() {
  redirect("/inbox");
}
```

- [ ] **Step 6: Edit `frontend/src/app/layout.tsx`** to set the app title

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NB Research Tool",
  description: "Homicide sentencing tracker for NB Media Productions",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

- [ ] **Step 7: Verify dev server runs**

```bash
cd frontend
pnpm dev   # (or npm run dev)
# Visit http://localhost:3000 → should redirect to /inbox (will 404, fine for now)
```

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Next.js + Tailwind + shadcn/ui"
```

---

### Task 20: API client + auth helpers

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/lib/types.ts`

- [ ] **Step 1: Create `frontend/src/lib/types.ts`**

```ts
export type CaseStatus =
  | "new" | "reviewing" | "approved" | "rejected"
  | "foia_filed" | "records_received" | "archived";

export interface CaseListItem {
  id: string;
  defendant_name: string;
  defendant_age: number | null;
  defendant_hometown: string | null;
  sentencing_date: string;
  state: string;
  county: string | null;
  sentence_text: string | null;
  sentence_type: string | null;
  content_score: number;
  status: CaseStatus;
  summary: string | null;
  created_at: string;
}

export interface CaseArticle {
  id: string;
  url: string;
  title: string | null;
  source_name: string;
  source_type: string;
  published_at: string | null;
}

export interface CaseDetail extends CaseListItem {
  victims: { name: string | null; age: number | null }[];
  charges: { statute: string | null; degree: string | null; description: string }[];
  docket_number: string | null;
  judge_name: string | null;
  court_name: string | null;
  prosecuting_office: string | null;
  investigating_agency: string | null;
  sentence_years: number | null;
  notes: string | null;
  articles: CaseArticle[];
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "researcher";
  is_active: boolean;
  last_login_at: string | null;
}

export interface SourceItem {
  id: string;
  name: string;
  type: string;
  is_active: boolean;
  last_run_at: string | null;
  last_success_at: string | null;
  items_fetched_24h: number;
  items_extracted_24h: number;
  consecutive_failures: number;
}
```

- [ ] **Step 2: Create `frontend/src/lib/api.ts`**

```ts
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  loginWithGoogle: (idToken: string) =>
    call("/api/auth/login", { method: "POST", body: JSON.stringify({ id_token: idToken }) }),
  logout: () => call("/api/auth/logout", { method: "POST" }),
  me: () => call("/api/auth/me"),

  listCases: (params: Record<string, string | number> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    );
    return call(`/api/cases?${qs.toString()}`);
  },
  getCase: (id: string) => call(`/api/cases/${id}`),
  updateCase: (id: string, patch: object) =>
    call(`/api/cases/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  transitionCase: (id: string, action: string, note?: string) =>
    call(`/api/cases/${id}/transition`, {
      method: "POST",
      body: JSON.stringify({ action, note }),
    }),

  listSources: () => call("/api/sources"),
  toggleSource: (id: string, isActive: boolean) =>
    call(`/api/sources/${id}`, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) }),
  runSource: (id: string) => call(`/api/sources/${id}/run`, { method: "POST" }),

  listUsers: () => call("/api/users"),
  updateUser: (id: string, patch: object) =>
    call(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
};
```

- [ ] **Step 3: Create `frontend/src/lib/auth.ts`**

```ts
import { api } from "./api";
import type { User } from "./types";

export async function getCurrentUser(): Promise<User | null> {
  try {
    return await api.me() as User;
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib
git commit -m "feat(frontend): API client + auth helpers + shared types"
```

---

### Task 21: Login page with Google sign-in

**Files:**
- Create: `frontend/src/app/login/page.tsx`
- Modify: `frontend/src/app/layout.tsx` (add Google script)

- [ ] **Step 1: Add Google client script to layout**

In `frontend/src/app/layout.tsx`, add inside `<body>` before children:
```tsx
<script src="https://accounts.google.com/gsi/client" async defer></script>
```

- [ ] **Step 2: Create `frontend/src/app/login/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

declare global {
  interface Window { google?: any }
}

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      if (window.google) {
        window.google.accounts.id.initialize({
          client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
          hd: "nbmediaproductions.com",
          callback: handleCredentialResponse,
        });
        window.google.accounts.id.renderButton(
          document.getElementById("gsi-button")!,
          { theme: "outline", size: "large", text: "signin_with", width: 280 }
        );
        clearInterval(interval);
      }
    }, 100);
    return () => clearInterval(interval);
  }, []);

  async function handleCredentialResponse(resp: { credential: string }) {
    try {
      await api.loginWithGoogle(resp.credential);
      router.push("/inbox");
    } catch (e: any) {
      setError(e.message.includes("403")
        ? "Sign-in restricted to @nbmediaproductions.com accounts."
        : "Sign-in failed. Try again.");
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50">
      <div className="bg-white rounded-2xl shadow-sm border p-10 max-w-md w-full text-center">
        <h1 className="text-2xl font-semibold tracking-tight">NB Research Tool</h1>
        <p className="text-slate-600 mt-2 mb-8">
          Internal use only — sign in with your @nbmediaproductions.com account.
        </p>
        <div className="flex justify-center"><div id="gsi-button" /></div>
        {error && (
          <p className="text-red-600 text-sm mt-6">{error}</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Test manually**

Set up an OAuth client in Google Cloud Console (Web application, authorized JS origin: `http://localhost:3000`), put client ID in `frontend/.env.local`.

```bash
cd frontend && pnpm dev
# Visit http://localhost:3000/login, click sign-in button.
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/login frontend/src/app/layout.tsx
git commit -m "feat(frontend): Google sign-in login page"
```

---

### Task 22: Protected layout + Inbox page

**Files:**
- Create: `frontend/src/components/app-shell.tsx`
- Create: `frontend/src/app/inbox/page.tsx`
- Create: `frontend/src/components/case-row.tsx`

- [ ] **Step 1: Create `frontend/src/components/app-shell.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

const NAV = [
  { href: "/inbox", label: "Inbox" },
  { href: "/sources", label: "Sources", admin: true },
  { href: "/users", label: "Users", admin: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.me()
      .then((u) => setUser(u as User))
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading…</div>;
  }
  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/inbox" className="font-semibold tracking-tight">
            NB Research
          </Link>
          <nav className="flex items-center gap-6 text-sm">
            {NAV.filter(n => !n.admin || user.role === "admin").map(n => (
              <Link
                key={n.href} href={n.href}
                className={`hover:text-slate-900 ${pathname?.startsWith(n.href) ? "text-slate-900 font-medium" : "text-slate-500"}`}
              >{n.label}</Link>
            ))}
            <span className="text-slate-400">|</span>
            <span className="text-slate-700">{user.email}</span>
            <button
              onClick={async () => { await api.logout(); router.push("/login"); }}
              className="text-slate-500 hover:text-red-600"
            >Sign out</button>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto p-6">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/case-row.tsx`**

```tsx
"use client";
import Link from "next/link";
import type { CaseListItem } from "@/lib/types";

function Stars({ score }: { score: number }) {
  return <span className="text-amber-500">{"★".repeat(score)}<span className="text-slate-300">{"★".repeat(5 - score)}</span></span>;
}

const STATUS_PILL: Record<string, string> = {
  new: "bg-blue-100 text-blue-700",
  reviewing: "bg-amber-100 text-amber-700",
  approved: "bg-emerald-100 text-emerald-700",
  rejected: "bg-slate-200 text-slate-600",
  foia_filed: "bg-violet-100 text-violet-700",
  records_received: "bg-green-100 text-green-700",
  archived: "bg-slate-100 text-slate-500",
};

export function CaseRow({ c }: { c: CaseListItem }) {
  return (
    <Link href={`/case/${c.id}`} className="block bg-white rounded-lg border p-4 hover:border-slate-400 transition">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <Stars score={c.content_score} />
            <span className="font-medium truncate">{c.defendant_name}{c.defendant_age != null ? `, ${c.defendant_age}` : ""}</span>
            {c.defendant_hometown && <span className="text-slate-500 text-sm truncate">· {c.defendant_hometown}</span>}
          </div>
          <div className="text-sm text-slate-700 mt-1">{c.sentence_text || "—"}</div>
          <div className="text-sm text-slate-500 mt-0.5">
            {[c.county, c.state].filter(Boolean).join(", ")} · {c.sentencing_date}
          </div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_PILL[c.status] || "bg-slate-100"}`}>
          {c.status.replace("_", " ")}
        </span>
      </div>
    </Link>
  );
}
```

- [ ] **Step 3: Create `frontend/src/app/inbox/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { CaseRow } from "@/components/case-row";
import { api } from "@/lib/api";
import type { CaseListItem } from "@/lib/types";

const STATUS_OPTIONS = ["new", "reviewing", "approved", "rejected",
                        "foia_filed", "records_received", "archived"];

export default function InboxPage() {
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("new");
  const [state, setState] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number> = { page, page_size: 25 };
    if (status) params.status = status;
    if (state) params.state = state;
    if (q) params.q = q;
    api.listCases(params)
      .then((r: any) => { setCases(r.items); setTotal(r.total); })
      .finally(() => setLoading(false));
  }, [page, status, state, q]);

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight mr-auto">Inbox</h1>
        <select value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}
                className="border rounded-md px-2 py-1 text-sm bg-white">
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
        </select>
        <input value={state} onChange={(e) => { setPage(1); setState(e.target.value.toUpperCase()); }}
               placeholder="State (e.g. TX)" maxLength={2}
               className="border rounded-md px-2 py-1 text-sm bg-white w-24" />
        <input value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }}
               placeholder="Search…" className="border rounded-md px-2 py-1 text-sm bg-white" />
      </div>

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : cases.length === 0 ? (
        <p className="text-slate-500">No cases match.</p>
      ) : (
        <div className="space-y-3">
          {cases.map(c => <CaseRow key={c.id} c={c} />)}
        </div>
      )}

      <div className="mt-6 flex items-center justify-between text-sm text-slate-600">
        <span>{total} total · page {page} of {Math.max(1, Math.ceil(total / 25))}</span>
        <div className="space-x-2">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
                  className="px-3 py-1 border rounded-md disabled:opacity-50">Prev</button>
          <button onClick={() => setPage(page + 1)} disabled={page * 25 >= total}
                  className="px-3 py-1 border rounded-md disabled:opacity-50">Next</button>
        </div>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 4: Test manually**

```bash
cd frontend && pnpm dev
# Sign in, then visit /inbox. Should show your test cases.
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/inbox frontend/src/components
git commit -m "feat(frontend): protected layout + inbox page"
```

---

### Task 23: Case detail page

**Files:**
- Create: `frontend/src/app/case/[id]/page.tsx`
- Create: `frontend/src/components/case-form.tsx`

- [ ] **Step 1: Create `frontend/src/components/case-form.tsx`**

```tsx
"use client";
import { useState } from "react";
import type { CaseDetail } from "@/lib/types";

const FIELDS: { key: keyof CaseDetail; label: string }[] = [
  { key: "defendant_name", label: "Defendant" },
  { key: "defendant_age", label: "Age" },
  { key: "defendant_hometown", label: "Hometown" },
  { key: "court_name", label: "Court" },
  { key: "county", label: "County" },
  { key: "state", label: "State" },
  { key: "docket_number", label: "Docket #" },
  { key: "judge_name", label: "Judge" },
  { key: "prosecuting_office", label: "Prosecuting office" },
  { key: "investigating_agency", label: "Investigating agency" },
];

export function CaseForm({ c, onSave }: { c: CaseDetail; onSave: (patch: any) => void }) {
  const [form, setForm] = useState<any>(c);
  return (
    <div className="grid grid-cols-2 gap-3">
      {FIELDS.map(f => (
        <label key={String(f.key)} className="text-sm">
          <span className="block text-slate-500 mb-1">{f.label}</span>
          <input
            value={form[f.key] ?? ""}
            onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
            className="w-full border rounded-md px-2 py-1 bg-white"
          />
        </label>
      ))}
      <label className="col-span-2 text-sm">
        <span className="block text-slate-500 mb-1">Notes</span>
        <textarea rows={3}
          value={form.notes ?? ""}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          className="w-full border rounded-md px-2 py-1 bg-white"
        />
      </label>
      <div className="col-span-2 flex justify-end">
        <button
          onClick={() => {
            const patch: any = {};
            FIELDS.forEach(f => {
              if (form[f.key] !== c[f.key]) patch[f.key] = form[f.key];
            });
            if (form.notes !== c.notes) patch.notes = form.notes;
            if (Object.keys(patch).length) onSave(patch);
          }}
          className="bg-slate-900 text-white text-sm rounded-md px-4 py-1.5">
          Save changes
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/app/case/[id]/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CaseForm } from "@/components/case-form";
import { api } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";

const ACTIONS = [
  { action: "approve", label: "Approve", color: "bg-emerald-600" },
  { action: "needs_info", label: "Needs info", color: "bg-amber-500" },
  { action: "reject", label: "Reject", color: "bg-slate-500" },
  { action: "mark_foia_filed", label: "FOIA filed", color: "bg-violet-600" },
];

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [c, setC] = useState<CaseDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.getCase(id).then((d: any) => setC(d)).catch(e => setErr(e.message));
  }, [id]);

  async function save(patch: any) {
    const updated = await api.updateCase(id, patch);
    setC(updated as CaseDetail);
  }

  async function transition(action: string) {
    const updated = await api.transitionCase(id, action);
    setC(updated as CaseDetail);
  }

  if (err) return <AppShell><div className="text-red-600">{err}</div></AppShell>;
  if (!c) return <AppShell><div className="text-slate-500">Loading…</div></AppShell>;

  return (
    <AppShell>
      <button onClick={() => router.push("/inbox")} className="text-sm text-slate-500 hover:text-slate-900 mb-4">
        ← Back to inbox
      </button>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 bg-white rounded-lg border p-6">
          <h1 className="text-xl font-semibold tracking-tight">
            {c.defendant_name}
            {c.defendant_age != null && <span className="text-slate-500 font-normal">, {c.defendant_age}</span>}
          </h1>
          <p className="text-slate-600 text-sm mt-1">
            {[c.county, c.state].filter(Boolean).join(", ")} · {c.sentencing_date}
          </p>
          <p className="mt-2 text-slate-800">{c.sentence_text || "Sentence details pending."}</p>
          {c.summary && <p className="mt-4 text-slate-700">{c.summary}</p>}

          <hr className="my-6" />
          <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-3">Editable fields</h2>
          <CaseForm c={c} onSave={save} />

          <hr className="my-6" />
          <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-3">Actions</h2>
          <div className="flex gap-2">
            {ACTIONS.map(a => (
              <button key={a.action} onClick={() => transition(a.action)}
                      className={`text-white text-sm rounded-md px-4 py-1.5 ${a.color}`}>
                {a.label}
              </button>
            ))}
          </div>
        </div>

        <aside className="bg-white rounded-lg border p-6">
          <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-3">Sources</h2>
          {c.articles.length === 0 && <p className="text-slate-500 text-sm">No articles linked.</p>}
          <ul className="space-y-2 text-sm">
            {c.articles.map(a => (
              <li key={a.id}>
                <a href={a.url} target="_blank" rel="noreferrer"
                   className="text-blue-700 hover:underline line-clamp-2">{a.title || a.url}</a>
                <div className="text-slate-500 text-xs">{a.source_name}</div>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 3: Test manually**

Click into a case from inbox. Edit a field, click Save, refresh. Confirm persistence.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/case frontend/src/components/case-form.tsx
git commit -m "feat(frontend): case detail page with edit + actions"
```

---

### Task 24: Sources page (admin)

**Files:**
- Create: `frontend/src/app/sources/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/sources/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";
import type { SourceItem } from "@/lib/types";

function statusOf(s: SourceItem) {
  if (!s.is_active) return { label: "off", color: "bg-slate-300" };
  if (s.consecutive_failures >= 3) return { label: "failing", color: "bg-red-500" };
  if (s.consecutive_failures > 0) return { label: "warn", color: "bg-amber-500" };
  if (!s.last_success_at) return { label: "new", color: "bg-slate-400" };
  return { label: "ok", color: "bg-emerald-500" };
}

export default function SourcesPage() {
  const [items, setItems] = useState<SourceItem[]>([]);

  async function load() {
    const r: any = await api.listSources();
    setItems(r.items);
  }
  useEffect(() => { load(); }, []);

  return (
    <AppShell>
      <h1 className="text-xl font-semibold tracking-tight mb-6">Sources</h1>
      <table className="w-full bg-white rounded-lg border overflow-hidden text-sm">
        <thead className="bg-slate-100 text-slate-600">
          <tr>
            <th className="text-left p-3"></th>
            <th className="text-left p-3">Name</th>
            <th className="text-left p-3">Type</th>
            <th className="text-right p-3">Fetched 24h</th>
            <th className="text-right p-3">Extracted 24h</th>
            <th className="text-left p-3">Last run</th>
            <th className="p-3"></th>
          </tr>
        </thead>
        <tbody>
          {items.map(s => {
            const st = statusOf(s);
            return (
              <tr key={s.id} className="border-t">
                <td className="p-3"><span className={`inline-block w-2.5 h-2.5 rounded-full ${st.color}`} /></td>
                <td className="p-3 font-medium">{s.name}</td>
                <td className="p-3 text-slate-600">{s.type}</td>
                <td className="p-3 text-right">{s.items_fetched_24h}</td>
                <td className="p-3 text-right">{s.items_extracted_24h}</td>
                <td className="p-3 text-slate-600">{s.last_run_at ?? "—"}</td>
                <td className="p-3 text-right space-x-2">
                  <button onClick={async () => { await api.runSource(s.id); load(); }}
                          className="text-xs border rounded-md px-2 py-1">Run now</button>
                  <button onClick={async () => { await api.toggleSource(s.id, !s.is_active); load(); }}
                          className="text-xs border rounded-md px-2 py-1">
                    {s.is_active ? "Pause" : "Activate"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </AppShell>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/sources
git commit -m "feat(frontend): admin sources health page"
```

---

### Task 25: Users page (admin)

**Files:**
- Create: `frontend/src/app/users/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/users/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export default function UsersPage() {
  const [items, setItems] = useState<User[]>([]);

  async function load() {
    const r: any = await api.listUsers();
    setItems(r.items);
  }
  useEffect(() => { load(); }, []);

  return (
    <AppShell>
      <h1 className="text-xl font-semibold tracking-tight mb-6">Users</h1>
      <table className="w-full bg-white rounded-lg border overflow-hidden text-sm">
        <thead className="bg-slate-100 text-slate-600">
          <tr>
            <th className="text-left p-3">Email</th>
            <th className="text-left p-3">Name</th>
            <th className="text-left p-3">Role</th>
            <th className="text-left p-3">Active</th>
            <th className="text-left p-3">Last login</th>
            <th className="p-3"></th>
          </tr>
        </thead>
        <tbody>
          {items.map(u => (
            <tr key={u.id} className="border-t">
              <td className="p-3">{u.email}</td>
              <td className="p-3 text-slate-700">{u.full_name ?? "—"}</td>
              <td className="p-3">{u.role}</td>
              <td className="p-3">{u.is_active ? "yes" : "no"}</td>
              <td className="p-3 text-slate-600">{u.last_login_at ?? "—"}</td>
              <td className="p-3 text-right space-x-2">
                <button
                  onClick={async () => {
                    await api.updateUser(u.id, { role: u.role === "admin" ? "researcher" : "admin" });
                    load();
                  }}
                  className="text-xs border rounded-md px-2 py-1">
                  {u.role === "admin" ? "Demote" : "Promote"}
                </button>
                <button
                  onClick={async () => { await api.updateUser(u.id, { is_active: !u.is_active }); load(); }}
                  className="text-xs border rounded-md px-2 py-1">
                  {u.is_active ? "Deactivate" : "Activate"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </AppShell>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/users
git commit -m "feat(frontend): admin users page"
```

---

## Phase 6 — Operations

### Task 26: Content scoring + daily summary

**Files:**
- Create: `backend/app/scoring/__init__.py`
- Create: `backend/app/scoring/score.py`
- Create: `backend/app/notifications/__init__.py`
- Create: `backend/app/notifications/slack.py`
- Create: `backend/tests/test_scoring.py`
- Modify: `backend/app/workers/pipeline.py` (call scoring)
- Modify: `backend/app/workers/tasks.py` (daily summary task)

- [ ] **Step 1: Write failing test**

`backend/tests/test_scoring.py`:
```python
from app.scoring.score import compute_content_score

def test_life_no_parole_scores_high():
    s = compute_content_score({
        "sentence_type": "life_no_parole",
        "victims": [{"name": "x", "age": None}],
        "charges": [{"description": "first-degree murder"}],
    })
    assert s >= 4

def test_multiple_victims_increases_score():
    s = compute_content_score({
        "sentence_type": "years", "sentence_years": 10,
        "victims": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
        "charges": [{"description": "manslaughter"}],
    })
    assert s >= 3

def test_minimum_score_is_1():
    s = compute_content_score({"sentence_type": "years", "sentence_years": 2,
                                "victims": [], "charges": []})
    assert s >= 1
```

- [ ] **Step 2: Create `backend/app/scoring/__init__.py`** (empty)

- [ ] **Step 3: Create `backend/app/scoring/score.py`**

```python
def compute_content_score(extracted: dict) -> int:
    score = 1
    st = extracted.get("sentence_type")
    if st in ("death", "life_no_parole"):
        score += 2
    elif st == "life":
        score += 1
    elif st == "years" and (extracted.get("sentence_years") or 0) >= 40:
        score += 1
    victims = extracted.get("victims") or []
    if len(victims) > 1:
        score += 1
    if any((v.get("age") or 99) < 18 for v in victims):
        score += 1
    return max(1, min(5, score))
```

- [ ] **Step 4: Wire scoring into `backend/app/workers/pipeline.py`**

In `process_article`, after constructing the `Case`:
```python
from app.scoring.score import compute_content_score
# ...
case.content_score = compute_content_score(data)
```

(Add the same line when merging into an existing case so re-extracts can recompute.)

- [ ] **Step 5: Create `backend/app/notifications/__init__.py`** (empty)

- [ ] **Step 6: Create `backend/app/notifications/slack.py`**

```python
import httpx
from app.config import settings

def post_summary(text: str) -> None:
    if not settings.slack_webhook_url:
        return
    try:
        httpx.post(settings.slack_webhook_url, json={"text": text}, timeout=10.0)
    except Exception:
        pass  # don't fail the pipeline on notification failure
```

- [ ] **Step 7: Add daily summary task to `backend/app/workers/tasks.py`**

```python
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from app.models import Case
from app.notifications.slack import post_summary

@celery_app.task
def post_daily_summary():
    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        new_count = db.query(func.count(Case.id)).filter(Case.created_at >= since).scalar() or 0
        high = (db.query(func.count(Case.id))
                  .filter(Case.created_at >= since, Case.content_score >= 4).scalar() or 0)
    finally:
        db.close()
    base = settings.frontend_url
    post_summary(f"NB Research: {new_count} new cases overnight, {high} high-priority. {base}/inbox")
    return {"new": new_count, "high": high}
```

- [ ] **Step 8: Add to Beat schedule in `backend/app/workers/celery_app.py`**

```python
celery_app.conf.beat_schedule["daily_summary"] = {
    "task": "app.workers.tasks.post_daily_summary",
    "schedule": crontab(hour=13, minute=30),   # ~9 AM US Eastern
}
```

- [ ] **Step 9: Run tests, verify PASS**

- [ ] **Step 10: Commit**

```bash
git add backend/app/scoring backend/app/notifications backend/app/workers backend/tests/test_scoring.py
git commit -m "feat(scoring): content score + Slack daily summary"
```

---

### Task 27: systemd units + Caddyfile + deploy script

**Files:**
- Create: `deploy/systemd/nbtool-api.service`
- Create: `deploy/systemd/nbtool-frontend.service`
- Create: `deploy/systemd/nbtool-worker.service`
- Create: `deploy/systemd/nbtool-beat.service`
- Create: `deploy/Caddyfile.example`
- Create: `scripts/deploy.sh`

- [ ] **Step 1: Create `deploy/systemd/nbtool-api.service`**

```ini
[Unit]
Description=NB Research API (FastAPI)
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=nbtool
Group=nbtool
WorkingDirectory=/opt/nbtool/backend
EnvironmentFile=/opt/nbtool/backend/.env
ExecStart=/opt/nbtool/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Create `deploy/systemd/nbtool-frontend.service`**

```ini
[Unit]
Description=NB Research Frontend (Next.js)
After=network.target

[Service]
Type=simple
User=nbtool
Group=nbtool
WorkingDirectory=/opt/nbtool/frontend
EnvironmentFile=/opt/nbtool/frontend/.env.local
ExecStart=/usr/bin/node node_modules/next/dist/bin/next start -p 3000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Create `deploy/systemd/nbtool-worker.service`**

```ini
[Unit]
Description=NB Research Celery Worker
After=network.target redis-server.service postgresql.service

[Service]
Type=simple
User=nbtool
Group=nbtool
WorkingDirectory=/opt/nbtool/backend
EnvironmentFile=/opt/nbtool/backend/.env
ExecStart=/opt/nbtool/backend/.venv/bin/celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Create `deploy/systemd/nbtool-beat.service`**

```ini
[Unit]
Description=NB Research Celery Beat
After=network.target redis-server.service

[Service]
Type=simple
User=nbtool
Group=nbtool
WorkingDirectory=/opt/nbtool/backend
EnvironmentFile=/opt/nbtool/backend/.env
ExecStart=/opt/nbtool/backend/.venv/bin/celery -A app.workers.celery_app beat --loglevel=info
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 5: Create `deploy/Caddyfile.example`**

```
research.nbmediaproductions.com {
    # Frontend
    handle {
        reverse_proxy 127.0.0.1:3000
    }

    # API
    handle_path /api/* {
        rewrite * /api{uri}
        reverse_proxy 127.0.0.1:8000
    }

    handle /health {
        reverse_proxy 127.0.0.1:8000
    }

    encode gzip
    log {
        output file /var/log/caddy/nbtool.log
    }
}
```

- [ ] **Step 6: Create `scripts/deploy.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

cd /opt/nbtool
echo "==> pulling latest"
git pull --ff-only

echo "==> backend deps"
cd backend
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> db migrations"
alembic upgrade head

echo "==> frontend build"
cd ../frontend
pnpm install --frozen-lockfile
pnpm build

echo "==> restart services"
sudo systemctl restart nbtool-api.service
sudo systemctl restart nbtool-worker.service
sudo systemctl restart nbtool-beat.service
sudo systemctl restart nbtool-frontend.service

echo "==> health"
curl -fsS http://127.0.0.1:8000/health
echo
echo "deploy OK"
```

```bash
chmod +x scripts/deploy.sh
```

- [ ] **Step 7: One-time VPS setup commands (documented in README)**

```bash
# As root, once:
adduser --system --group --home /opt/nbtool nbtool
chown -R nbtool:nbtool /opt/nbtool

# Install services
cp /opt/nbtool/deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now nbtool-api nbtool-frontend nbtool-worker nbtool-beat

# Caddy
cp /opt/nbtool/deploy/Caddyfile.example /etc/caddy/Caddyfile
systemctl reload caddy
```

- [ ] **Step 8: Commit**

```bash
git add deploy scripts/deploy.sh
git commit -m "ops: systemd units + Caddyfile + deploy script"
```

---

### Task 28: Backups + Sentry + recall eval

**Files:**
- Create: `scripts/backup.sh`
- Create: `scripts/eval_recall.py`
- Modify: `backend/app/main.py` (init Sentry)

- [ ] **Step 1: Create `scripts/backup.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Env:
#   PGUSER, PGPASSWORD, PGDATABASE, PGHOST  (Postgres connection)
#   B2_BUCKET, B2_KEY_ID, B2_APP_KEY        (Backblaze creds)

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TMP_DIR=$(mktemp -d)
DUMP_FILE="$TMP_DIR/nbtool-${STAMP}.sql.gz"

echo "==> dumping $PGDATABASE"
pg_dump --no-owner --no-privileges "$PGDATABASE" | gzip -9 > "$DUMP_FILE"

echo "==> uploading to B2 bucket $B2_BUCKET"
# Requires b2 CLI installed and authorized: b2 authorize-account $B2_KEY_ID $B2_APP_KEY
b2 upload-file "$B2_BUCKET" "$DUMP_FILE" "nbtool/${STAMP}.sql.gz"

echo "==> pruning local dumps older than 7 days"
find /opt/nbtool/backups -name "*.sql.gz" -mtime +7 -delete 2>/dev/null || true

rm -rf "$TMP_DIR"
echo "backup OK"
```

```bash
chmod +x scripts/backup.sh
```

Schedule via cron:
```cron
# /etc/cron.d/nbtool-backup
0 3 * * * nbtool /opt/nbtool/scripts/backup.sh >> /var/log/nbtool-backup.log 2>&1
```

- [ ] **Step 2: Add Sentry init to `backend/app/main.py`**

Insert near the top, before `app = FastAPI(...)`:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        environment=settings.environment,
        traces_sample_rate=0.05,
    )
```

- [ ] **Step 3: Create `scripts/eval_recall.py`**

```python
"""Weekly recall eval:
sample N homicide sentencings from a curated external feed (manually maintained list),
check whether each appears in our DB. Log the recall percentage.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import date, timedelta
from app.db import SessionLocal
from app.models import Case
from app.dedup.matcher import normalize_name, find_matching_case

# Maintained by a researcher in a JSON file checked into the repo.
# Each entry: { defendant_name, sentencing_date (YYYY-MM-DD), state, source_url }
SAMPLE_FILE = os.path.join(os.path.dirname(__file__), "recall_sample.json")

def main():
    import json
    if not os.path.exists(SAMPLE_FILE):
        print("No recall sample file; skipping.")
        return
    samples = json.load(open(SAMPLE_FILE))
    db = SessionLocal()
    try:
        hits = 0
        for s in samples:
            sd = date.fromisoformat(s["sentencing_date"])
            m = find_matching_case(db, s["defendant_name"], sd, s["state"])
            if m is not None:
                hits += 1
        recall = hits / len(samples) if samples else 0
        print(f"Recall: {hits}/{len(samples)} = {recall:.1%}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
```

Schedule via cron:
```cron
0 4 * * 1 nbtool /opt/nbtool/backend/.venv/bin/python /opt/nbtool/scripts/eval_recall.py >> /var/log/nbtool-recall.log 2>&1
```

- [ ] **Step 4: Create empty seed `scripts/recall_sample.json`** with a few hand-curated entries

```json
[
  {
    "defendant_name": "EXAMPLE PLACEHOLDER",
    "sentencing_date": "2026-05-19",
    "state": "TX",
    "source_url": "https://example.com/article"
  }
]
```

(A researcher will replace this with real samples; the script handles the empty case gracefully.)

- [ ] **Step 5: Update README** with setup instructions

Create `README.md` at repo root summarizing: prerequisites, one-time setup, deploy command, env vars.

- [ ] **Step 6: Commit**

```bash
git add scripts backend/app/main.py README.md
git commit -m "ops: backups + Sentry + recall eval script"
```

---

## Plan Self-Review

**1. Spec coverage check:**

| Spec section | Tasks |
|---|---|
| §2 Goals (95% recall) | Task 28 (recall eval) |
| §4 Users (roles, domain restriction) | Tasks 5, 7, 18 |
| §6 Architecture | Tasks 2, 3, 19, 27 |
| §7 Tech stack | All |
| §8 Data model | Task 4 (all models + migration) |
| §9 Pipeline | Tasks 8–13, 26 (scoring) |
| §10 Screens | Tasks 19–25 (5 screens covered) |
| §11 Auth | Tasks 5, 6, 7 |
| §12 Deployment | Tasks 27, 28 |
| §14 Risks/mitigations | Task 28 (backups, Sentry); per-source health in Task 13 |

Phase A coverage is complete. Phase B (Task 4 in §9 — auto-enrichment via SerpAPI/CourtListener) and Phase C (FOIA filing via MuckRock) are explicitly out of scope for this plan and will get their own plans.

**2. Placeholder scan:** No `TBD`, `TODO`, "implement later", or "add appropriate X" patterns found. Each step contains actual code or a concrete command.

**3. Type consistency:**
- `process_article` returns `dict` consistently
- `IngestedArticle` dataclass used in `BaseSource.fetch()` and `process_article` (Tasks 8, 9, 10, 13) — consistent
- Enum string values match between models (Task 4) and pipeline (Task 13) — `"new"`, `"extracted"`, `"no_match"`, etc.
- `current_user` / `admin_required` signatures match between definition (Task 7) and usage (Tasks 14, 17, 18)
- API client method names (Task 20) align with backend route paths (Tasks 6, 14–18)

**4. Scope check:** 28 tasks across 6 phases of work. Each task is bite-sized (single component) with TDD steps. Total realistic effort: 3–4 weeks for a 1-2 engineer team.

---

## Execution Handoff

Plan complete and saved to [docs/superpowers/plans/2026-05-20-nb-media-sentencing-tracker-phase-a.md](docs/superpowers/plans/2026-05-20-nb-media-sentencing-tracker-phase-a.md).

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a single long-running session where I'm in the loop.

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
