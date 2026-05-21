from google.oauth2 import id_token
from google.auth.transport import requests as g_requests
from app.config import settings


class EmailDomainNotAllowed(Exception):
    pass


def _allowed_domains() -> list[str]:
    return [d.strip().lower() for d in settings.allowed_email_domains.split(",") if d.strip()]


def verify_id_token(token: str) -> dict:
    """Verify a Google ID token and return normalized claims.

    Raises EmailDomainNotAllowed if the email doesn't end with one of the
    configured allowed domains, isn't verified, or is missing.
    """
    payload = id_token.verify_oauth2_token(
        token, g_requests.Request(), settings.google_client_id
    )

    email = payload.get("email", "").lower()
    if not payload.get("email_verified"):
        raise EmailDomainNotAllowed("email not verified by Google")

    allowed = _allowed_domains()
    if not any(email.endswith("@" + d) for d in allowed):
        raise EmailDomainNotAllowed(
            f"email must end in one of: {', '.join('@' + d for d in allowed)}"
        )

    return {
        "google_sub": payload["sub"],
        "email": email,
        "full_name": payload.get("name"),
    }
