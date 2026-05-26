import json
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from app.config import settings
from app.extraction.prompts import (
    EXTRACTION_SYSTEM_PROMPT, EXTRACTION_PROMPT_VERSION, build_user_prompt,
)

EXTRACTION_MODEL = "gemini-2.5-pro"

REQUIRED_KEYS = {
    "is_homicide_sentencing", "defendant_name", "victims", "charges",
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


def _build_model() -> GenerativeModel:
    """Constructs a fresh GenerativeModel (kept as a helper so tests can patch it)."""
    return GenerativeModel(EXTRACTION_MODEL, system_instruction=EXTRACTION_SYSTEM_PROMPT)


def extract_case_fields(article_text: str, source_name: str) -> dict:
    """Run LLM extraction via Vertex AI Gemini 2.5 Pro.

    Returns dict with keys: status, data, model, prompt_version, error.
    Possible status: 'extracted' | 'no_match' | 'failed'.

    Authentication is via Google Application Default Credentials (ADC).
    Set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON file.
    """
    _ensure_initialized()
    try:
        model = _build_model()
        response = model.generate_content(
            build_user_prompt(article_text, source_name),
            generation_config=GenerationConfig(
                # Was 2000; truncation caused json_decode errors on verbose
                # articles. 8000 leaves comfortable headroom.
                max_output_tokens=8000,
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
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

    if not data.get("is_homicide_sentencing"):
        return {"status": "no_match", "data": data, "model": EXTRACTION_MODEL,
                "prompt_version": EXTRACTION_PROMPT_VERSION}

    return {"status": "extracted", "data": data, "model": EXTRACTION_MODEL,
            "prompt_version": EXTRACTION_PROMPT_VERSION}
