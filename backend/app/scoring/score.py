def compute_content_score(extracted: dict) -> int:
    score = 1
    st = extracted.get("sentence_type")
    if st in ("death", "life_no_parole"):
        score += 2
    elif st == "life":
        score += 1
    elif st == "years" and (extracted.get("sentence_years") or 0) >= 40:
        score += 1
    victims = extracted.get("victims") or []
    if len(victims) > 0:
        score += 1
    if len(victims) > 1:
        score += 1
    if any((v.get("age") or 99) < 18 for v in victims):
        score += 1
    return max(1, min(5, score))
