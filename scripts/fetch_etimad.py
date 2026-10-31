"""Pull Etimad tender listings through Apify.

    python scripts/fetch_etimad.py [--max 300] [--keywords CRM]
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from kurrasa.config import Env

API = "https://api.apify.com/v2"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "research" / "raw" / "etimad"

ACTOR = "gulfdata~etimad-tenders-monitor"


def build_input(max_items: int, keywords: str) -> dict:
    return {
        "keywords": keywords,
        "pageSize": 24,                       # Etimad serves 24 per page regardless
        "maxPages": -(-max_items // 24),
        "monitorMode": False,                 # True only returns tenders unseen by earlier runs
        "useResidentialProxy": True,          # Etimad blocks datacenter IPs
        "proxyCountryCode": "SA",
        "includeRaw": True,
    }


def run_actor(actor: str, actor_input: dict, token: str) -> tuple[dict, list]:
    headers = {"Authorization": f"Bearer {token}"}
    run = requests.post(f"{API}/acts/{actor}/runs", json=actor_input, headers=headers).json()["data"]
    print(f"run {run['id']} started")

    while run["status"] in ("READY", "RUNNING"):
        time.sleep(10)
        run = requests.get(f"{API}/actor-runs/{run['id']}", headers=headers).json()["data"]

    if run["status"] != "SUCCEEDED":
        raise RuntimeError(f"run {run['id']} ended with status {run['status']}")

    items = requests.get(f"{API}/datasets/{run['defaultDatasetId']}/items", headers=headers).json()
    return run, items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=300)
    parser.add_argument("--keywords", default="")
    args = parser.parse_args()

    actor_input = build_input(args.max, args.keywords)
    run, items = run_actor(ACTOR, actor_input, Env().APIFY_TOKEN)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = OUT_DIR / f"tenders_{stamp}.json"
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    # Run details so the pull can be traced back to Apify
    meta = {
        "actor": ACTOR,
        "input": actor_input,
        "run_id": run["id"],
        "started_at": run["startedAt"],
        "finished_at": run["finishedAt"],
        "item_count": len(items),
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"saved {len(items)} records to {out.name}")


if __name__ == "__main__":
    main()
