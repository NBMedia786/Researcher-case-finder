import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://nbtool:nbtool@localhost:5432/nbtool"
    redis_url: str = "redis://localhost:6379/0"

    google_client_id: str = ""
    google_client_secret: str = ""
    jwt_secret: str = "dev-secret-change-me"
    # Comma-separated list of allowed email domains (e.g. "nbmediaproductions.com,gmail.com").
    # The OAuth login flow only accepts emails ending in one of these domains.
    allowed_email_domains: str = "nbmediaproductions.com"
    admin_emails: str = ""

    # Vertex AI (Gemini 2.5 Pro on Google Cloud)
    # Auth happens via Google Application Default Credentials (ADC).
    gcp_project_id: str = ""
    gcp_vertex_region: str = "us-central1"
    # Path to GCP service-account JSON. Pydantic loads this from .env but
    # Google's client libraries look for it in os.environ, so we also
    # propagate it below via _propagate_google_creds().
    google_application_credentials: str = ""

    newsapi_key: str = ""
    mediastack_key: str = ""
    # Google News via SerpAPI ($50/mo paid) — replicates web-search coverage
    serpapi_key: str = ""
    # Tavily LLM-optimized web search (free tier: 1000 searches/month)
    tavily_api_key: str = ""
    # CourtListener federal court records (free; token raises rate limit)
    courtlistener_api_token: str = ""
    # NewsData.io (free 200/day)
    newsdata_api_key: str = ""
    # GNews.io (free 100/day)
    gnews_api_key: str = ""

    # Only ingest cases whose sentencing happened within this many days.
    # Set to a higher number for retrospectives / catch-up runs.
    sentencing_lookback_days: int = 3

    environment: str = "development"
    log_level: str = "INFO"
    # DEV ONLY: skip session-cookie auth and treat every request as the
    # first admin user. Set to "true" in local .env to use the UI without
    # signing in. NEVER set on the VPS — anyone hitting the public URL
    # would have admin access.
    dev_bypass_auth: bool = False
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    sentry_dsn: str = ""
    slack_webhook_url: str = ""


settings = Settings()


def _propagate_google_creds() -> None:
    """Push GOOGLE_APPLICATION_CREDENTIALS from .env into os.environ.

    pydantic-settings only assigns to the Settings object; it doesn't update
    os.environ. The google-auth / vertexai client libraries read directly
    from os.environ, so without this they fail with "default credentials
    not found" even when the .env value is present.
    """
    if settings.google_application_credentials and "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials


_propagate_google_creds()
