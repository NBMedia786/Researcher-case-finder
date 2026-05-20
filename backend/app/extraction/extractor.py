import json
from anthropic import Anthropic
from app.config import settings
from app.extraction.prompts import (
    EXTRACTION_SYSTEM_PROMPT, EXTRACTION_PROMPT_VERSION, build_user_prompt,
)

EXTRACTION_MODEL = "claude-haiku-4-5-20251001"

REQUIRED_KEYS = {
    "is_homicide_sentencing", "defendant_name", "victims", "charges",
    "sentence_type", "sentencing_date", "state", "summary",
}

def extract_case_fields(article_text: str, source_name: str) -> dict:
    """Run LLM extraction. Returns dict with keys: status, data, model, prompt_version, error."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    try:
        msg = client.messages.create(
            model=EXTRACTION_MODEL,
            max_tokens=2000,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(article_text, source_name)}],
        )
        text = msg.content[0].text.strip()
        # The model is instructed to output pure JSON, but be defensive:
        if text.startswith("```"):
            text = text.strip("` \n")
            if text.startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return {"status": "failed", "error": f"json_decode: {e}",
                "model": EXTRACTION_MODEL, "prompt_version": EXTRACTION_PROMPT_VERSION}
    except Exception as e:
        return {"status": "failed", "error": f"llm_error: {e}",
                "model": EXTRACTION_MODEL, "prompt_version": EXTRACTION_PROMPT_VERSION}

    if not REQUIRED_KEYS.issubset(set(data.keys())):
        return {"status": "failed", "error": "missing required keys",
                "data": data, "model": EXTRACTION_MODEL,
                "prompt_version": EXTRACTION_PROMPT_VERSION}

    if not data.get("is_homicide_sentencing"):
        return {"status": "no_match", "data": data, "model": EXTRACTION_MODEL,
                "prompt_version": EXTRACTION_PROMPT_VERSION}

    return {"status": "extracted", "data": data, "model": EXTRACTION_MODEL,
            "prompt_version": EXTRACTION_PROMPT_VERSION}
