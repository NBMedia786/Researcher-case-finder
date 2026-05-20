from app.scoring.score import compute_content_score

def test_life_no_parole_scores_high():
    s = compute_content_score({
        "sentence_type": "life_no_parole",
        "victims": [{"name": "x", "age": None}],
        "charges": [{"description": "first-degree murder"}],
    })
    assert s >= 4

def test_multiple_victims_increases_score():
    s = compute_content_score({
        "sentence_type": "years", "sentence_years": 10,
        "victims": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
        "charges": [{"description": "manslaughter"}],
    })
    assert s >= 3

def test_minimum_score_is_1():
    s = compute_content_score({"sentence_type": "years", "sentence_years": 2,
                                "victims": [], "charges": []})
    assert s >= 1
