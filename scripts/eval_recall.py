"""Weekly recall eval:
sample N homicide sentencings from a curated external feed (manually maintained list),
check whether each appears in our DB. Log the recall percentage.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import date, timedelta
from app.db import SessionLocal
from app.models import Case
from app.dedup.matcher import normalize_name, find_matching_case

# Maintained by a researcher in a JSON file checked into the repo.
# Each entry: { defendant_name, sentencing_date (YYYY-MM-DD), state, source_url }
SAMPLE_FILE = os.path.join(os.path.dirname(__file__), "recall_sample.json")

def main():
    import json
    if not os.path.exists(SAMPLE_FILE):
        print("No recall sample file; skipping.")
        return
    samples = json.load(open(SAMPLE_FILE))
    db = SessionLocal()
    try:
        hits = 0
        for s in samples:
            sd = date.fromisoformat(s["sentencing_date"])
            m = find_matching_case(db, s["defendant_name"], sd, s["state"])
            if m is not None:
                hits += 1
        recall = hits / len(samples) if samples else 0
        print(f"Recall: {hits}/{len(samples)} = {recall:.1%}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
