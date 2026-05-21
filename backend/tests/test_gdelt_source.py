from unittest.mock import patch, MagicMock
from app.sources.gdelt import GdeltSource

SAMPLE_RESPONSE = {
    "articles": [
        {
            "url": "https://example.com/gdelt-article-1",
            "url_mobile": "",
            "title": "Man sentenced to life for murder in Texas",
            "seendate": "20260519T120000Z",
            "socialimage": "",
            "domain": "houstonchronicle.com",
            "language": "English",
            "sourcecountry": "United States",
        }
    ]
}


def test_fetch_returns_articles():
    src = GdeltSource(config={"queries": ["sentenced AND murder sourcecountry:US"]})
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_RESPONSE
    with patch("app.sources.gdelt.httpx.get", return_value=mock_resp):
        out = list(src.fetch())
    assert len(out) == 1
    assert out[0].url == "https://example.com/gdelt-article-1"
    assert out[0].source_type == "gdelt"
