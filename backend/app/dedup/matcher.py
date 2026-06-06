import re
import unicodedata
from datetime import date, timedelta
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models import Case

# Placeholder value used in cases.state when Gemini couldn't extract a
# real US state for the article. Treated as a wildcard during dedup so
# we don't split the same defendant into two case rows just because one
# article was clearer than another about location.
STATE_UNKNOWN = "??"

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
# Generational/professional suffixes stripped so "John Smith Jr" matches
# "John Smith" and "John Smith Jr."
_SUFFIX_RE = re.compile(
    r"\b(jr|sr|ii|iii|iv|v|esq|md|phd|dds|cpa)\.?$",
    re.IGNORECASE,
)

def normalize_name(name: str) -> str:
    if not name:
        return ""
    # NFKD then strip combining marks to fold accents
    nfkd = unicodedata.normalize("NFKD", name)
    no_accent = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = no_accent.lower()
    no_punct = _PUNCT_RE.sub("", lowered)
    collapsed = _WS_RE.sub(" ", no_punct).strip()
    # Repeatedly strip trailing suffix tokens ("john smith jr ii" -> "john smith")
    prev = None
    while prev != collapsed:
        prev = collapsed
        collapsed = _SUFFIX_RE.sub("", collapsed).strip()
    return collapsed


def first_last_key(normalized_name: str) -> str:
    """Return 'first last' token of a normalized name, dropping middle names.

    Used as a fuzzy match key to catch the same defendant across articles
    that disagree on the middle name — e.g. one article says
    "Michael Cornelius Watson" and another says "Michael Watson". When
    the date + state also match, that's the same case.
    """
    tokens = normalized_name.split()
    if len(tokens) <= 1:
        return normalized_name
    return f"{tokens[0]} {tokens[-1]}"

def _state_clause(state_upper: str):
    """Return a SQLAlchemy filter for matching state, treating '??' as a
    wildcard on either side.

    - Incoming state is '??' (Gemini couldn't extract one) → don't filter
      on state at all; we'll trust the date+name match. Caller is
      expected to UPGRADE the matched case's state if the new article
      later turns out to know it.
    - Incoming state is a real US state → match existing rows with that
      state OR rows still stuck at '??' (so the second article can heal
      the first article's missing-state row).

    Without this, the same defendant ends up split into two cases just
    because one article was clearer about location than another (we saw
    this with Kouri Richins, Mackenzie Shirilla, Tanner Horner, etc.).
    """
    if state_upper == STATE_UNKNOWN:
        return None  # caller: don't apply a state filter
    return or_(Case.state == state_upper, Case.state == STATE_UNKNOWN)


def find_matching_case(
    db: Session,
    defendant_name: str,
    sentencing_date: date,
    state: str,
    window_days: int = 3,
) -> Case | None:
    """Return existing case for the same defendant + state, else None.

    Strategy:
    1. First look within `window_days` of `sentencing_date` (the safe case
       — same defendant, dates close together, almost certainly same event).
    2. If no date-window match, fall back to (defendant_name + state) only.
       Same defendant in the same US state being sentenced for two
       different homicide cases is extremely rare in practice; the more
       common cause of date mismatch is one article reporting the original
       sentencing date and another using the article's publish date as a
       fallback. The researcher can split via the UI if a real duplicate
       collision happens.

    State is matched leniently — '??' (unknown) on either side is treated
    as a wildcard so the second article about the same defendant can
    merge in and heal the missing state, instead of creating a duplicate.
    """
    if not defendant_name or not state:
        return None
    nname = normalize_name(defendant_name)
    if not nname:
        return None
    state_upper = state.upper()
    state_clause = _state_clause(state_upper)

    if sentencing_date is not None:
        lo = sentencing_date - timedelta(days=window_days)
        hi = sentencing_date + timedelta(days=window_days)
        # 1a. Exact normalized-name match within date window.
        q = (
            db.query(Case)
            .filter(Case.defendant_name_normalized == nname)
            .filter(Case.sentencing_date.between(lo, hi))
        )
        if state_clause is not None:
            q = q.filter(state_clause)
        match = q.first()
        if match is not None:
            return match
        # 1b. Fuzzy fallback: same first + last token, same state, same date
        # window. Catches "Michael Cornelius Watson" vs "Michael Watson"
        # for the same sentencing. Date+state gating keeps this safe from
        # common-name false positives.
        fl_key = first_last_key(nname)
        cq = db.query(Case).filter(Case.sentencing_date.between(lo, hi))
        if state_clause is not None:
            cq = cq.filter(state_clause)
        candidates = cq.all()
        for cand in candidates:
            if first_last_key(cand.defendant_name_normalized or "") == fl_key:
                return cand

    # Fall back to defendant + state, no date constraint (exact only —
    # the fuzzy fallback above is intentionally date-gated to stay safe).
    q = db.query(Case).filter(Case.defendant_name_normalized == nname)
    if state_clause is not None:
        q = q.filter(state_clause)
    return q.first()

def merge_extracted_into_case(case: Case, extracted: dict) -> None:
    """Fill empty fields on `case` with values from `extracted`. Never overwrite."""
    fillable = (
        "defendant_age", "defendant_hometown", "sentence_text", "sentence_years",
        "sentence_type", "court_name", "county", "docket_number", "judge_name",
        "prosecuting_office", "investigating_agency", "summary",
    )
    for f in fillable:
        if getattr(case, f, None) in (None, "", 0) and extracted.get(f):
            setattr(case, f, extracted[f])

    # Heal a previously-unknown state when the new article does know
    # one. Without this, every '??' case row would stay stuck at '??'
    # forever, since the matcher's wildcard treats it as already-known.
    incoming_state = (extracted.get("state") or "").upper()[:2]
    if (
        case.state == STATE_UNKNOWN
        and incoming_state
        and incoming_state != STATE_UNKNOWN
    ):
        case.state = incoming_state
