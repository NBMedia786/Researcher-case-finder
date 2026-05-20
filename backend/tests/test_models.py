from app.models import User, Case, Article, Source, AuditLog


def test_models_importable():
    assert User.__tablename__ == "users"
    assert Case.__tablename__ == "cases"
    assert Article.__tablename__ == "articles"
    assert Source.__tablename__ == "sources"
    assert AuditLog.__tablename__ == "audit_log"


def test_case_has_required_columns():
    cols = {c.name for c in Case.__table__.columns}
    required = {
        "id", "defendant_name", "defendant_name_normalized",
        "sentencing_date", "state", "county",
        "status", "content_score", "created_at",
    }
    assert required.issubset(cols)
