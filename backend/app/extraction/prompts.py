EXTRACTION_PROMPT_VERSION = "v2"


# Default criteria + name — used as fallback when the pipeline runs
# without an active Topic row (shouldn't happen in normal flow, but
# defends against migration ordering bugs).
DEFAULT_TOPIC_NAME = "Homicide Sentencings"
DEFAULT_TOPIC_CRITERIA = (
    "An article reporting that a defendant has been sentenced in court "
    "for a homicide-related offense — murder, manslaughter, or related "
    "charges. Set is_match=true only when a sentencing has actually "
    "occurred (not merely an arrest, indictment, trial, or appeal) AND "
    "the underlying offense is a homicide."
)


SHARED_SCHEMA = """{
  "is_match": bool,                  // true only if the article matches the
                                     // topic's match criteria below
  "defendant_name": string|null,     // primary subject of the article
                                     // (defendant, accused, suspect, etc.)
  "defendant_age": int|null,
  "defendant_hometown": string|null,
  "victims": [{"name": string|null, "age": int|null}],
  "charges": [{"statute": string|null, "degree": string|null,
               "description": string}],
  "sentence_text": string|null,      // verbatim sentence phrase (if any)
  "sentence_type": "years"|"life"|"life_no_parole"|"death"|null,
  "sentence_years": int|null,
  "sentencing_date": "YYYY-MM-DD"|null,  // the most relevant date for this
                                          // topic — sentencing date for
                                          // sentencing topics, incident or
                                          // arrest date for other topics
  "court_name": string|null,
  "county": string|null,
  "state": string|null,              // 2-letter US state code
  "docket_number": string|null,
  "judge_name": string|null,
  "prosecuting_office": string|null,
  "investigating_agency": string|null,
  "summary": string                  // one-paragraph plain-English summary
}"""


def build_system_prompt(topic_name: str, topic_criteria: str) -> str:
    """Build the Gemini system prompt for a specific topic."""
    name = (topic_name or DEFAULT_TOPIC_NAME).strip()
    criteria = (topic_criteria or DEFAULT_TOPIC_CRITERIA).strip()
    return f"""You extract structured facts about US news events matching a
specific topic, from news articles. You ALWAYS reply with a single JSON
object, no markdown, no commentary.

CURRENT TOPIC: {name}

MATCH CRITERIA:
{criteria}

Schema:
{SHARED_SCHEMA}

Set is_match=false if:
- the article does not satisfy the MATCH CRITERIA above
- the event described is outside the United States
- the article is opinion/analysis/retrospective, not a news report of a
  specific recent event
- the relevant event has not yet occurred (e.g. an upcoming hearing)

If a field doesn't apply to this topic (e.g. sentence_years for a
kidnapping article), set it to null. Always include the field key.
"""


def build_user_prompt(article_text: str, source_name: str) -> str:
    return f"""Source: {source_name}

Article:
{article_text[:8000]}

Extract the schema above as a single JSON object."""
