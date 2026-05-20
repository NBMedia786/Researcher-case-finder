from app.workers.celery_app import celery_app

def test_celery_app_configured():
    assert celery_app.main == "nbtool"
    task_queues = celery_app.conf.task_queues
    assert (task_queues and "default" in task_queues) or celery_app.conf.task_default_queue == "default"

def test_celery_beat_schedule_has_pipeline():
    schedule = celery_app.conf.beat_schedule
    assert "daily_full_sweep" in schedule
    assert "light_sweep" in schedule
