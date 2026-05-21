import json
from unittest.mock import patch, MagicMock
from app.extraction.extractor import extract_case_fields, EXTRACTION_MODEL

SAMPLE_TEXT = """John Doe, 34, of Houston, was sentenced Monday to life
without parole after being convicted of first-degree murder
in the 2024 killing of his neighbor Maria Lopez, 28.
Judge Jane Smith of the Harris County Criminal District Court
imposed the sentence. The Houston Police Department investigated."""

VALID_LLM_JSON = {
    "is_homicide_sentencing": True,
    "defendant_name": "John Doe",
    "defendant_age": 34,
    "defendant_hometown": "Houston, TX",
    "victims": [{"name": "Maria Lopez", "age": 28}],
    "charges": [{"statute": None, "degree": "first-degree", "description": "first-degree murder"}],
    "sentence_text": "life without parole",
    "sentence_type": "life_no_parole",
    "sentence_years": None,
    "sentencing_date": "2026-05-19",
    "court_name": "Harris County Criminal District Court",
    "county": "Harris",
    "state": "TX",
    "docket_number": None,
    "judge_name": "Jane Smith",
    "prosecuting_office": None,
    "investigating_agency": "Houston Police Department",
    "summary": "John Doe sentenced to life without parole for first-degree murder of Maria Lopez.",
}

def test_extract_returns_structured_fields():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(VALID_LLM_JSON))]
    with patch("app.extraction.extractor.AnthropicVertex") as MockAnth:
        MockAnth.return_value.messages.create.return_value = mock_msg
        result = extract_case_fields(SAMPLE_TEXT, source_name="Local News")
    assert result["status"] == "extracted"
    assert result["data"]["defendant_name"] == "John Doe"
    assert result["data"]["state"] == "TX"
    assert result["model"] == EXTRACTION_MODEL

def test_extract_marks_no_match_when_not_homicide_sentencing():
    bad = dict(VALID_LLM_JSON, is_homicide_sentencing=False)
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(bad))]
    with patch("app.extraction.extractor.AnthropicVertex") as MockAnth:
        MockAnth.return_value.messages.create.return_value = mock_msg
        result = extract_case_fields("unrelated text", source_name="X")
    assert result["status"] == "no_match"
