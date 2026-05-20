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
