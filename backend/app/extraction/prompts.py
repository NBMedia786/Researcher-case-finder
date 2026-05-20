EXTRACTION_PROMPT_VERSION = "v1"

EXTRACTION_SYSTEM_PROMPT = """You extract structured facts about US homicide
sentencings from news articles. You ALWAYS reply with a single JSON object,
no markdown, no commentary.

Schema:
{
  "is_homicide_sentencing": bool,   // true only if a US criminal court has
                                    // just sentenced someone for murder,
                                    // homicide, or manslaughter
  "defendant_name": string|null,
  "defendant_age": int|null,
  "defendant_hometown": string|null,
  "victims": [{"name": string|null, "age": int|null}],
  "charges": [{"statute": string|null, "degree": string|null,
               "description": string}],
  "sentence_text": string|null,     // verbatim sentence phrase
  "sentence_type": "years"|"life"|"life_no_parole"|"death"|null,
  "sentence_years": int|null,       // numeric only, null if life/death
  "sentencing_date": "YYYY-MM-DD"|null,  // date of sentencing
  "court_name": string|null,
  "county": string|null,            // county name without 'County' suffix
  "state": string|null,             // 2-letter US state code
  "docket_number": string|null,
  "judge_name": string|null,
  "prosecuting_office": string|null,
  "investigating_agency": string|null,
  "summary": string                  // one-paragraph plain-English summary
}

Set is_homicide_sentencing=false if:
- the article is about an arrest, charge, conviction without sentencing
- the case is not a US case
- the case is not homicide/murder/manslaughter
- the article is opinion/analysis, not a news report of sentencing
"""

def build_user_prompt(article_text: str, source_name: str) -> str:
    return f"""Source: {source_name}

Article:
{article_text[:8000]}

Extract the schema above as a single JSON object."""
