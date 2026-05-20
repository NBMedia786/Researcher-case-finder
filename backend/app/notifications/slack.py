import httpx
from app.config import settings

def post_summary(text: str) -> None:
    if not settings.slack_webhook_url:
        return
    try:
        httpx.post(settings.slack_webhook_url, json={"text": text}, timeout=10.0)
    except Exception:
        pass  # don't fail the pipeline on notification failure
