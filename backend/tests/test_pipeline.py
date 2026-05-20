from datetime import date
from unittest.mock import patch, MagicMock
from app.workers.pipeline import process_article
from app.sources.base import IngestedArticle

ARTICLE = IngestedArticle(
    url="https://example.com/a", title="Sentenced", published_at=None,
    raw_text="John Doe sentenced to life...", source_name="Ex", source_type="news_api",
)

EXTRACTED = {
    "status": "extracted",
    "model": "claude-haiku-4-5",
    "prompt_version": "v1",
    "data": {
        "is_homicide_sentencing": True,
        "defendant_name": "John Doe",
        "defendant_age": 34,
        "defendant_hometown": "Houston, TX",
        "victims": [], "charges": [],
        "sentence_text": "life", "sentence_type": "life",
        "sentence_years": None, "sentencing_date": "2026-05-19",
        "court_name": None, "county": "Harris", "state": "TX",
        "docket_number": None, "judge_name": None,
        "prosecuting_office": None, "investigating_agency": None,
        "summary": "summary",
    },
}

def test_process_article_creates_case_and_article(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with patch("app.workers.pipeline.extract_case_fields", return_value=EXTRACTED), \
         patch("app.workers.pipeline.find_matching_case", return_value=None):
        out = process_article(db, ARTICLE)
    assert out["created_case"] is True
    db.add.assert_called()
    db.commit.assert_called()
