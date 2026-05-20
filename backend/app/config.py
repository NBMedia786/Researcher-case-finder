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
