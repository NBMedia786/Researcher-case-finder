import json
import time
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from app.config import settings
from app.extraction.prompts import (
    EXTRACTION_PROMPT_VERSION, build_system_prompt, build_user_prompt,
    DEFAULT_TOPIC_NAME, DEFAULT_TOPIC_CRITERIA,
)

EXTRACTION_MODEL = "gemini-2.5-pro"

# Vertex Gemini rate-limits at the project/region level — under load it
# returns HTTP 429 ("Resource exhausted"). Without retries we'd lose
# real homicide-sentencing cases just because the API was busy.
#
# Backoff sequence with these values: 5s, 10s, 20s, 40s, 80s, 120s, 120s, 120s
# (capped at MAX_DELAY). Total worst-case wait per article: ~515s. Higher
# than the article-scrape and DB-write costs combined, but it's only paid
# when Vertex actually rate-limits us — most articles finish on attempt 1.
_RATE_LIMIT_MAX_ATTEMPTS = 8
_RATE_LIMIT_BASE_DELAY = 5     # seconds — doubles each attempt
_RATE_LIMIT_MAX_DELAY = 120    # cap so we don't sleep 640s on the final attempt

REQUIRED_KEYS = {
    "is_match", "defendant_name", "victims", "charges",
    "sentence_type", "sentencing_date", "state", "summary",
}

_initialized = False


def _ensure_initialized() -> None:
    """Initialize vertexai once per process. Auth via GOOGLE_APPLICATION_CREDENTIALS."""
    global _initialized
    if _initialized:
        return
    vertexai.init(project=settings.gcp_project_id, location=settings.gcp_vertex_region)
    _initialized = True


def _build_model(system_prompt: str) -> GenerativeModel:
    """Constructs a fresh GenerativeModel (kept as a helper so tests can patch it)."""
    return GenerativeModel(EXTRACTION_MODEL, system_instruction=system_prompt)


def extract_case_fields(
    article_text: str,
    source_name: str,
    topic_name: str = DEFAULT_TOPIC_NAME,
    topic_criteria: str = DEFAULT_TOPIC_CRITERIA,
) -> dict:
    """Run LLM extraction via Vertex AI Gemini 2.5 Pro.

    Returns dict with keys: status, data, model, prompt_version, error.
    Possible status: 'extracted' | 'no_match' | 'failed'.

    The Gemini system prompt is built dynamically from topic_name +
    topic_criteria so the same extractor handles every topic (homicide
    sentencings, kidnappings, etc.) without code changes.

    Authentication is via Google Application Default Credentials (ADC).
    Set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON file.
    """
    _ensure_initialized()
    try:
        system_prompt = build_system_prompt(topic_name, topic_criteria)
        model = _build_model(system_prompt)
        prompt = build_user_prompt(article_text, source_name)
        gen_config = GenerationConfig(
            # Was 2000; truncation caused json_decode errors on verbose
            # articles. 8000 leaves comfortable headroom.
            max_output_tokens=8000,
            temperature=0.1,
            response_mime_type="application/json",
        )
        # Retry loop for 429 ("Resource exhausted") — without this we lose
        # real homicide-sentencing cases when Vertex briefly rate-limits us.
        response = None
        last_err: Exception | None = None
        for attempt in range(_RATE_LIMIT_MAX_ATTEMPTS):
            try:
                response = model.generate_content(prompt, generation_config=gen_config)
                break
            except Exception as e:
                last_err = e
                if "429" not in str(e) and "Resource exhausted" not in str(e):
                    # Non-rate-limit error — surface immediately
                    raise
                if attempt == _RATE_LIMIT_MAX_ATTEMPTS - 1:
                    raise
                delay = min(_RATE_LIMIT_BASE_DELAY * (2 ** attempt), _RATE_LIMIT_MAX_DELAY)
                time.sleep(delay)
        if response is None:
            raise last_err or RuntimeError("rate-limit retry exhausted")
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("` \n")
            if text.startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        # Gemini occasionally returns a JSON array wrapping the object,
        # e.g. `[{...}]`. Unwrap.
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            return {"status": "failed",
                    "error": f"unexpected output shape: {type(data).__name__}",
                    "model": EXTRACTION_MODEL, "prompt_version": EXTRACTION_PROMPT_VERSION}
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

    if not data.get("is_match"):
        return {"status": "no_match", "data": data, "model": EXTRACTION_MODEL,
                "prompt_version": EXTRACTION_PROMPT_VERSION}

    return {"status": "extracted", "data": data, "model": EXTRACTION_MODEL,
            "prompt_version": EXTRACTION_PROMPT_VERSION}
