from app.workers.celery_app import celery_app

@celery_app.task
def run_full_pipeline():
    return "full pipeline triggered"

@celery_app.task
def run_light_pipeline():
    return "light pipeline triggered"
