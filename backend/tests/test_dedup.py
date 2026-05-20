from app.dedup.matcher import normalize_name

def test_normalize_strips_punctuation():
    assert normalize_name("John Q. Doe Jr.") == "john q doe jr"

def test_normalize_collapses_whitespace():
    assert normalize_name("  John   Doe  ") == "john doe"

def test_normalize_handles_unicode():
    assert normalize_name("José García") == "jose garcia"
