from app.dedup.matcher import normalize_name

def test_normalize_strips_punctuation():
    # Suffixes like "Jr." are also stripped so "John Q. Doe Jr." matches "John Q. Doe"
    assert normalize_name("John Q. Doe Jr.") == "john q doe"


def test_normalize_strips_generational_suffixes():
    assert normalize_name("Cornelius Smith") == normalize_name("Cornelius Smith Jr.")
    assert normalize_name("Cornelius Smith") == normalize_name("Cornelius Smith Jr")
    assert normalize_name("Cornelius Smith") == normalize_name("Cornelius Smith II")
    assert normalize_name("Cornelius Smith Sr.") == normalize_name("Cornelius Smith")

def test_normalize_collapses_whitespace():
    assert normalize_name("  John   Doe  ") == "john doe"

def test_normalize_handles_unicode():
    assert normalize_name("José García") == "jose garcia"
