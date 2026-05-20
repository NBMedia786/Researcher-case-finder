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
