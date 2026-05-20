from app.sources.base import IngestedArticle, BaseSource


def test_ingested_article_dataclass():
    a = IngestedArticle(
        url="https://x.com/a", title="t", published_at=None,
        raw_text="body", source_name="X", source_type="news_api",
    )
    assert a.url == "https://x.com/a"


def test_base_source_requires_fetch():
    import pytest
    class S(BaseSource):
        name = "test"
        source_type = "news_api"
    s = S(config={})
    with pytest.raises(NotImplementedError):
        list(s.fetch())
