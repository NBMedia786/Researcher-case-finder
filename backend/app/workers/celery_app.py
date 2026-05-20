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
