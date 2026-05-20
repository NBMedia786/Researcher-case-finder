from unittest.mock import patch, MagicMock
from app.sources.newsapi import NewsAPISource

SAMPLE_RESPONSE = {
    "status": "ok",
    "articles": [
        {
            "url": "https://example.com/article-1",
            "title": "Man sentenced to life for murder",
            "publishedAt": "2026-05-19T12:00:00Z",
            "content": "A jury sentenced John Doe to life...",
            "description": "...",
            "source": {"name": "Example News"},
        }
    ],
}


def test_fetch_returns_articles():
    src = NewsAPISource(config={"api_key": "k", "queries": ["sentenced to life"]})
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_RESPONSE
    with patch("app.sources.newsapi.httpx.get", return_value=mock_resp):
        out = list(src.fetch())
    assert len(out) == 1
    assert out[0].url == "https://example.com/article-1"
    assert "sentenced" in out[0].title.lower()
    assert out[0].source_type == "news_api"
