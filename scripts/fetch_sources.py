"""Download the public source documents and record where they came from."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "research" / "raw"
MANIFEST = ROOT / "data" / "research" / "sources_manifest.json"

SOURCES = {
    "ksu_services_booklet_template.docx": "https://ps.ksu.edu.sa/sites/ps.ksu.edu.sa/files/users/user219/2025/%D9%86%D9%85%D9%88%D8%B0%D8%AC%20%D9%83%D8%B1%D8%A7%D8%B3%D8%A9%20(%D8%AE%D8%AF%D9%85%D8%A7%D8%AA).docx",
    "nca_ecc2_2024_en.pdf": "https://cdn.nca.gov.sa/api/files/public/upload/86e09090-44e4-481f-bc28-355673607654_ECC--2024-EN.pdf",
}

# SDAIA rejects scripted requests, so these were downloaded by hand in a browser
MANUAL = {
    "sdaia_pdpl_en.pdf": "https://sdaia.gov.sa/en/SDAIA/about/Documents/Personal%20Data%20English%20V2-23April2023-%20Reviewed-.pdf",
    "sdaia_data_transfer_regulation_en.pdf": "sdaia.gov.sa (exact URL not recorded; file RegulationonPersonalDataEN.pdf)",
}


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []

    for filename, url in SOURCES.items():
        content = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120).content
        (RAW / filename).write_bytes(content)
        manifest.append({
            "file": filename,
            "url": url,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
        print(f"saved {filename}")

    for filename, url in MANUAL.items():
        manifest.append({
            "file": filename,
            "url": url,
            "fetched_at": "manual browser download",
            "sha256": hashlib.sha256((RAW / filename).read_bytes()).hexdigest(),
        })

    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
