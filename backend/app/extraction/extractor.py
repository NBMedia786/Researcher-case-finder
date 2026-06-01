import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from app.config import settings
from app.extraction.prompts import (
    EXTRACTION_PROMPT_VERSION, build_system_prompt, build_user_prompt,
    DEFAULT_TOPIC_NAME, DEFAULT_TOPIC_CRITERIA,
)

log = logging.getLogger(__name__)

# vertexai 1.66's generate_content() has no timeout parameter — if the
# SDK hangs (slow Gemini response, stuck auth refresh, network blip) the
# worker waits forever and the whole pipeline stalls. Wrap each call in
# a ThreadPoolExecutor.submit().result(timeout=…) so we get a hard
# ceiling. On timeout the underlying thread leaks (it's still waiting on
# the SDK call), which is acceptable: this only triggers on a real hang,
# the leaked thread holds one HTTP connection's worth of resources, and
# the next backend restart cleans it up. Without this ceiling, our
# worker can lose hours per hang.
_GEMINI_HARD_TIMEOUT_SECONDS = 120

# Dedicated executor so a hung Gemini call doesn't block other work.
# max_workers high enough to absorb a few simultaneous hangs without
# starving live calls; the pipeline only ever has one Gemini call in
# flight at a time today so 4 is plenty of headroom.
_gemini_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gemini")

# Fallback chain — when the primary (2.5 Pro) is rate-limited or its
# daily quota is gone, fall through to progressively cheaper / higher-
# quota models so the pipeline keeps producing extractions instead of
# failing every article until midnight Pacific.
#
# Ordered by extraction quality (best first). Quotas roughly:
#   gemini-2.5-pro       — strictest free-tier quota (the one we burn first)
#   gemini-2.5-flash     — much higher quota, ~95% as good for this task
#   gemini-2.0-flash-001 — separate quota pool, still strong
#   gemini-1.5-pro-002   — legacy Pro, separate quota
MODEL_CHAIN = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash-001",
    "gemini-1.5-pro-002",
]

# Kept for backwards-compat (article.extraction_model column / tests) but
# the actual model used per article is tracked dynamically and reported
# in the response dict.
EXTRACTION_MODEL = MODEL_CHAIN[0]

# Per-model in-process cooldown — when a model 429s persistently we mark
# it cooled down for this long so subsequent articles in the run skip it
# without paying the retry latency. Resets on process restart.
_MODEL_COOLDOWN_SECONDS = 10 * 60  # 10 min
_model_cooldown_until: dict[str, float] = {}

# Per-model retry — small because we have a whole chain to lean on. A
# couple of quick retries absorbs transient blips; persistent 429s
# trigger fallback to the next model.
_MODEL_RETRIES = 2
_MODEL_RETRY_BASE_DELAY = 4     # seconds — doubles each attempt
_MODEL_RETRY_MAX_DELAY = 20

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


def _build_model(system_prompt: str, model_name: str = EXTRACTION_MODEL) -> GenerativeModel:
    """Constructs a fresh GenerativeModel (kept as a helper so tests can patch it)."""
    return GenerativeModel(model_name, system_instruction=system_prompt)


def _is_rate_limit_error(e: Exception) -> bool:
    s = str(e)
    return (
        "429" in s
        or "Resource exhausted" in s
        or "RESOURCE_EXHAUSTED" in s
        or "quota" in s.lower()
    )


def _call_one_model(
    model_name: str,
    system_prompt: str,
    prompt: str,
    gen_config: GenerationConfig,
) -> str:
    """Call a single model with limited in-model retries. Returns response
    text or raises. Rate-limit (429/quota) is left to the caller so it can
    decide whether to fall back to the next model in the chain.

    Each call is bounded by _GEMINI_HARD_TIMEOUT_SECONDS via a thread
    executor so a hung Vertex SDK call can't freeze the pipeline.
    Timeouts are treated like rate-limit errors (cool down + try next
    model) since "Gemini didn't respond" and "Gemini is throttling us"
    are operationally identical.
    """
    model = _build_model(system_prompt, model_name)
    last_err: Exception | None = None
    for attempt in range(_MODEL_RETRIES + 1):
        try:
            fut = _gemini_executor.submit(
                model.generate_content, prompt, generation_config=gen_config
            )
            try:
                resp = fut.result(timeout=_GEMINI_HARD_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                # Don't bother cancelling fut — the SDK call is blocking
                # in C/gRPC and can't be interrupted. Leak the thread;
                # process restart will reap it.
                raise TimeoutError(
                    f"Gemini {model_name} did not respond within "
                    f"{_GEMINI_HARD_TIMEOUT_SECONDS}s"
                )
            return resp.text.strip()
        except Exception as e:
            last_err = e
            # Timeouts and 429s both warrant falling forward to the next
            # model in the chain — they're not "this article is bad",
            # they're "this model is unavailable right now".
            if not _is_rate_limit_error(e) and not isinstance(e, TimeoutError):
                raise
            if attempt == _MODEL_RETRIES:
                raise
            delay = min(
                _MODEL_RETRY_BASE_DELAY * (2 ** attempt),
                _MODEL_RETRY_MAX_DELAY,
            )
            time.sleep(delay)
    if last_err:
        raise last_err
    raise RuntimeError("unreachable")


def _call_with_fallback(
    system_prompt: str,
    prompt: str,
    gen_config: GenerationConfig,
) -> tuple[str, str]:
    """Try each model in MODEL_CHAIN, falling forward on rate-limit errors.

    Returns (response_text, model_name_used).

    Models that 429 persistently get put in a 10-minute in-process
    cooldown so subsequent articles in the same run skip them
    immediately instead of re-paying retry latency.
    """
    now = time.monotonic()
    last_err: Exception | None = None
    tried_any = False
    for model_name in MODEL_CHAIN:
        wake = _model_cooldown_until.get(model_name, 0)
        if now < wake:
            log.info(
                "extractor: skipping %s — cooled down for another %.0fs",
                model_name, wake - now,
            )
            continue
        tried_any = True
        try:
            text = _call_one_model(model_name, system_prompt, prompt, gen_config)
            if model_name != MODEL_CHAIN[0]:
                log.info("extractor: fell back to %s", model_name)
            return text, model_name
        except Exception as e:
            last_err = e
            # Both 429s ("Gemini throttled us") and TimeoutErrors ("Gemini
            # didn't respond at all") mean this model is unavailable
            # right now — cool it down and fall forward.
            if _is_rate_limit_error(e) or isinstance(e, TimeoutError):
                _model_cooldown_until[model_name] = (
                    time.monotonic() + _MODEL_COOLDOWN_SECONDS
                )
                reason = "timeout" if isinstance(e, TimeoutError) else "rate-limited"
                log.warning(
                    "extractor: %s %s, cooling down %ds, trying next: %s",
                    model_name, reason, _MODEL_COOLDOWN_SECONDS, str(e)[:200],
                )
                continue
            # Non-rate-limit error from a model — bubble up; same error is
            # likely to happen with other models in the chain.
            raise

    # We get here only if every model 429'd or every model was already
    # cooled down. Surface the last 429 so the caller can mark the
    # article as failed and the operator can investigate.
    if not tried_any:
        raise RuntimeError("all models in MODEL_CHAIN are currently cooled down")
    raise last_err or RuntimeError("MODEL_CHAIN exhausted")


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
    model_used: str = MODEL_CHAIN[0]  # default for early-failure error paths
    try:
        system_prompt = build_system_prompt(topic_name, topic_criteria)
        prompt = build_user_prompt(article_text, source_name)
        gen_config = GenerationConfig(
            # Was 2000; truncation caused json_decode errors on verbose
            # articles. 8000 leaves comfortable headroom.
            max_output_tokens=8000,
            temperature=0.1,
            response_mime_type="application/json",
        )
        text, model_used = _call_with_fallback(system_prompt, prompt, gen_config)
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
                    "model": model_used, "prompt_version": EXTRACTION_PROMPT_VERSION}
    except json.JSONDecodeError as e:
        return {"status": "failed", "error": f"json_decode: {e}",
                "model": model_used, "prompt_version": EXTRACTION_PROMPT_VERSION}
    except Exception as e:
        return {"status": "failed", "error": f"llm_error: {e}",
                "model": model_used, "prompt_version": EXTRACTION_PROMPT_VERSION}

    if not REQUIRED_KEYS.issubset(set(data.keys())):
        return {"status": "failed", "error": "missing required keys",
                "data": data, "model": model_used,
                "prompt_version": EXTRACTION_PROMPT_VERSION}

    if not data.get("is_match"):
        return {"status": "no_match", "data": data, "model": model_used,
                "prompt_version": EXTRACTION_PROMPT_VERSION}

    return {"status": "extracted", "data": data, "model": model_used,
            "prompt_version": EXTRACTION_PROMPT_VERSION}
