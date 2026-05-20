from pathlib import Path
from unittest.mock import patch
from app.sources.doj import DOJSource

FIXTURE = (Path(__file__).parent / "fixtures" / "doj_rss.xml").read_text()


def test_filter_keeps_sentencing_items():
    src = DOJSource(config={"feeds": ["https://example/rss"]})
    with patch("app.sources.doj.httpx.get") as mget:
        mget.return_value.status_code = 200
        mget.return_value.text = FIXTURE
        out = list(src.fetch())
    urls = [a.url for a in out]
    assert "https://www.justice.gov/news/press-release/abc-123" in urls
    assert "https://www.justice.gov/news/press-release/xyz-999" not in urls
