"""Turn the latest raw Etimad pull into a clean CSV."""

import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "research" / "raw" / "etimad"
OUT = ROOT / "data" / "research" / "etimad_tenders.csv"

COLUMNS = [
    "tender_id", "reference_number", "title", "agency", "branch", "activity", "tender_type",
    "published", "last_enquiry", "submission_deadline", "enquiry_days", "submission_days",
    "booklet_fee_sar", "source_url",
]


def day(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value[:10]) if value else None


def clean(record: dict) -> dict:
    published = day(record["published_at"])
    enquiry = day(record["last_enquiry_date"])
    deadline = day(record["submission_deadline"])
    return {
        "tender_id": record["tender_id"],
        "reference_number": record["reference_number"],
        "title": " ".join(record["title"].split()),   # collapse stray tabs and double spaces
        "agency": record["agency"].strip(),
        "branch": (record["branch"] or "").strip(),
        "activity": (record["activity"] or "").strip(),
        "tender_type": record["tender_type"].strip(),
        "published": published.date() if published else "",
        "last_enquiry": enquiry.date() if enquiry else "",
        "submission_deadline": deadline.date() if deadline else "",
        "enquiry_days": (enquiry - published).days if enquiry and published else "",
        "submission_days": (deadline - published).days if deadline and published else "",
        "booklet_fee_sar": record["conditions_fee"],
        "source_url": record["source_url"],
    }


def main():
    latest = sorted(p for p in RAW.glob("tenders_*.json") if not p.name.endswith(".meta.json"))[-1]
    records = json.loads(latest.read_text(encoding="utf-8"))

    rows = {r["tender_id"]: clean(r) for r in records}   # keyed by id, so duplicates collapse
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig so Excel shows Arabic
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows.values())

    print(f"{len(records)} raw records from {latest.name} -> {len(rows)} clean rows in {OUT.name}")


if __name__ == "__main__":
    main()
