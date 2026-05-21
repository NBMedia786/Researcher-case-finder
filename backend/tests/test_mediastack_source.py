from unittest.mock import patch, MagicMock
from app.sources.mediastack import MediaStackSource

SAMPLE_RESPONSE = {
    "pagination": {"limit": 100, "offset": 0, "count": 1, "total": 1},
    "data": [
        {
            "author": "Jane Smith",
            "title": "Man sentenced to life for murder",
            "description": "A jury sentenced John Doe to life in prison without the possibility of parole.",
            "url": "https://example.com/mediastack-article-1",
            "source": "Houston Chronicle",
            "image": None,
            "category": "general",
            "language": "en",
            "country": "us",
            "published_at": "2026-05-19T12:00:00+00:00",
        }
    ],
}


def test_fetch_returns_articles():
    src = MediaStackSource(config={"api_key": "k", "queries": ["sentenced,murder"]})
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_RESPONSE
    with patch("app.sources.mediastack.httpx.get", return_value=mock_resp):
        out = list(src.fetch())
    assert len(out) == 1
    assert out[0].url == "https://example.com/mediastack-article-1"
    assert out[0].source_type == "news_api"
