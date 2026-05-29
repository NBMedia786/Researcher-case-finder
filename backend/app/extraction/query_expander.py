"""Smart query expansion via Gemini.

The researcher types a freeform description of what they're looking for
(e.g. "body concealment in murders" or "kidnap cases in florida that
ended in conviction") and we use the LLM to rewrite it into a short list
of search-API-friendly query variants.

Falls back to the manual comma/or splitter if Gemini fails for any
reason — better to run a less-optimal search than to error out.
"""
import json
import logging
from vertexai.generative_models import GenerationConfig
from app.extraction.extractor import _call_with_fallback, _ensure_initialized, MODEL_CHAIN

log = logging.getLogger(__name__)

# Cap on variants. More than this and we burn news-API quotas without
# meaningful coverage gain. 8 is comfortably above the typical user list.
_MAX_VARIANTS = 8

_EXPAND_SYSTEM_PROMPT = (
    "You are a search-query expander for a US homicide-sentencing news "
    "research tool. Researchers type freeform descriptions of cases they "
    "want to find, and you rewrite them into short search-API-friendly "
    "query variants for Google News / NewsAPI / Tavily.\n\n"
    "RULES (strict):\n"
    "1. Output ONLY a JSON array of strings. No prose, no markdown, no "
    "   leading/trailing commentary. Example: [\"kidnapping california\", "
    "   \"abduction california murder\"]\n"
    f"2. Return 3 to {_MAX_VARIANTS} variants. Fewer if the input is very "
    "   specific; more if it's broad.\n"
    "3. Each variant: 2-6 words, optimized for news-API keyword search.\n"
    "4. Preserve specific entities the user mentioned: state/county names, "
    "   specific charge types, named defendants.\n"
    "5. Add useful synonyms only when they would surface different articles: "
    "   homicide / murder / killing / slaying, kidnap / abduction, "
    "   sentenced / convicted, body / corpse / remains, etc.\n"
    "6. If the user already gave a comma-separated list, clean it up but "
    "   keep all their specific terms — don't drop any.\n"
    "7. Do NOT add unrelated terms or hallucinate jurisdictions.\n"
    "8. Output is case-insensitive but prefer lowercase for common nouns.\n"
)


def expand_query(user_text: str) -> tuple[list[str], str]:
    """Expand a freeform query into a list of search variants.

    Returns (variants, model_used). On any LLM failure, returns
    (_naive_split(user_text), 'fallback-split').
    """
    text = (user_text or "").strip()
    if not text:
        return [], "fallback-split"

    try:
        _ensure_initialized()
        user_prompt = f"Researcher input: {text}\n\nJSON array of search variants:"
        gen_config = GenerationConfig(
            max_output_tokens=400,
            temperature=0.2,
            response_mime_type="application/json",
        )
        raw, model_used = _call_with_fallback(_EXPAND_SYSTEM_PROMPT, user_prompt, gen_config)
        # Strip optional markdown fences just in case.
        if raw.startswith("```"):
            raw = raw.strip("` \n")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError(f"expected JSON array, got {type(parsed).__name__}")
        variants = [
            v.strip()
            for v in parsed
            if isinstance(v, str) and v.strip()
        ]
        # Dedupe (case-insensitive) preserving order.
        seen: set[str] = set()
        out: list[str] = []
        for v in variants:
            key = v.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(v)
        if not out:
            raise ValueError("LLM returned empty array")
        return out[:_MAX_VARIANTS], model_used
    except Exception as e:
        log.warning("expand_query: LLM failed (%s), falling back to manual split", e)
        return _naive_split(text), "fallback-split"


def _naive_split(text: str) -> list[str]:
    """Final fallback when Gemini is fully unavailable — keep the user's
    text as a single query rather than failing the search."""
    # Defer to the splitter in admin.py to keep behaviour consistent with
    # the non-smart path. Lazy import to avoid circular dependency.
    from app.api.admin import _split_queries
    parts = _split_queries(text)
    return parts or [text]
