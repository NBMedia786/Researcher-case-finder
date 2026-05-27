from datetime import date as date_cls, datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Article, Case, Topic
from app.sources.base import IngestedArticle
from app.extraction.extractor import extract_case_fields
from app.dedup.matcher import find_matching_case, normalize_name, merge_extracted_into_case
from app.scoring.score import compute_content_score

def _parse_date(s: str | None) -> date_cls | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None

def process_article(db: Session, ia: IngestedArticle, topic: Topic | None = None) -> dict:
    """Idempotent: same URL twice = no-op on second call.

    `topic` (optional) drives the LLM extraction prompt and the recency
    filter. When None, the legacy "Homicide Sentencings" defaults from
    extractor.py + settings.sentencing_lookback_days are used.
    """
    existing = db.query(Article).filter(Article.url == ia.url).one_or_none()
    if existing and existing.extraction_status in ("extracted", "no_match"):
        return {"skipped": True, "reason": "already processed"}

    article = existing or Article(
        url=ia.url, title=ia.title, published_at=ia.published_at,
        raw_text=ia.raw_text, source_name=ia.source_name,
        source_type=ia.source_type, extraction_status="pending",
    )
    if not existing:
        db.add(article)
        db.flush()  # so article.id exists

    # Use topic-specific extraction criteria if a topic is active.
    if topic is not None:
        result = extract_case_fields(
            ia.raw_text, ia.source_name,
            topic_name=topic.name,
            topic_criteria=topic.extraction_criteria,
        )
    else:
        result = extract_case_fields(ia.raw_text, ia.source_name)
    article.extracted_json = result.get("data")
    article.extraction_model = result.get("model")
    article.extraction_error = result.get("error")

    if result["status"] != "extracted":
        article.extraction_status = result["status"]
        db.commit()
        return {"skipped": True, "reason": result["status"]}

    data = result["data"]
    sentencing_date = _parse_date(data.get("sentencing_date"))
    state = (data.get("state") or "").upper()[:2]
    defendant = data.get("defendant_name") or ""

    # Fall back to the article's publish date when LLM couldn't extract a
    # specific sentencing date — news articles are usually published within
    # a day of the event. Researcher can correct via the UI.
    if not sentencing_date and ia.published_at:
        sentencing_date = ia.published_at.date()

    # If we still can't determine a date, drop it — we can't reliably
    # filter by recency without one.
    if not sentencing_date:
        article.extraction_status = "no_match"
        db.commit()
        return {"skipped": True, "reason": "no sentencing date extractable"}

    # Recency filter: use the active topic's recency_days if provided,
    # otherwise fall back to the global setting.
    recency_days = topic.recency_days if topic is not None else settings.sentencing_lookback_days
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=recency_days)
    if sentencing_date < cutoff:
        article.extraction_status = "no_match"
        db.commit()
        return {"skipped": True, "reason": f"event too old ({sentencing_date} < {cutoff})"}

    # Only DEFENDANT_NAME is strictly required. State can be filled in by
    # the researcher; missing state stored as empty string.
    if not defendant:
        article.extraction_status = "no_match"
        db.commit()
        return {"skipped": True, "reason": "missing defendant name"}
    if not state:
        state = "??"  # placeholder so the column (CHAR(2) NOT NULL) accepts it

    match = find_matching_case(db, defendant, sentencing_date, state)
    created = False
    if match is None:
        case = Case(
            defendant_name=defendant,
            defendant_name_normalized=normalize_name(defendant),
            defendant_age=data.get("defendant_age"),
            defendant_hometown=data.get("defendant_hometown"),
            victims=data.get("victims") or [],
            charges=data.get("charges") or [],
            sentence_text=data.get("sentence_text"),
            sentence_years=data.get("sentence_years"),
            sentence_type=data.get("sentence_type"),
            sentencing_date=sentencing_date,
            court_name=data.get("court_name"),
            county=data.get("county"),
            state=state,
            docket_number=data.get("docket_number"),
            judge_name=data.get("judge_name"),
            prosecuting_office=data.get("prosecuting_office"),
            investigating_agency=data.get("investigating_agency"),
            summary=data.get("summary"),
            status="new",
            topic_id=topic.id if topic is not None else None,
        )
        case.content_score = compute_content_score(data)
        db.add(case)
        db.flush()
        created = True
    else:
        case = match
        merge_extracted_into_case(case, data)
        case.content_score = compute_content_score(data)

    article.case_id = case.id
    article.extraction_status = "extracted"
    db.commit()
    return {"created_case": created, "case_id": str(case.id)}
