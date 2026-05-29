import sentry_sdk
from datetime import datetime, timezone
from sentry_sdk.integrations.fastapi import FastApiIntegration
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import api_router
from app.db import SessionLocal
from app.models import PipelineRun

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        environment=settings.environment,
        traces_sample_rate=0.05,
    )

app = FastAPI(title="NB Media Sentencing Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def _cleanup_zombie_pipelines() -> None:
    """Pipeline runs live as 'running' rows in the DB while a background
    thread does the actual work. If the backend is restarted mid-run, the
    thread dies but the row stays 'running' forever — a zombie that
    confuses the UI and blocks new runs (because run-search re-attaches
    to any existing 'running' row).

    On every startup, sweep any 'running' or 'cancelling' rows to
    'cancelled' so the UI clears and the next search can start fresh.
    """
    db = SessionLocal()
    try:
        zombies = (
            db.query(PipelineRun)
            .filter(PipelineRun.status.in_(["running", "cancelling"]))
            .all()
        )
        if not zombies:
            return
        for z in zombies:
            z.status = "cancelled"
            z.finished_at = datetime.now(timezone.utc)
            z.errors = list(z.errors or []) + ["interrupted by backend restart"]
        db.commit()
        print(f"[startup] cleaned {len(zombies)} zombie pipeline run(s)")
    except Exception as e:
        print(f"[startup] zombie cleanup failed: {type(e).__name__}: {e}")
        db.rollback()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
