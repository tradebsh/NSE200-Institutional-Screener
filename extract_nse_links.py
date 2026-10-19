import csv
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent

files = sorted(ROOT.glob("CF-Shareholding-Pattern-equities-*.csv"))

if not files:
    raise SystemExit("NSE shareholding CSV not found.")

source = files[0]
results = []
seen = set()

for source in files:
    with source.open("r", encoding="utf-8-sig", newline="") as f:
     reader = csv.DictReader(f)

    for row in reader:
        company = row["COMPANY"].strip()
        date_text = row["AS ON DATE"].strip()
        url = row["ACTION"].strip()

        parsed = urlparse(url)

        if (
            parsed.scheme != "https"
            or parsed.hostname != "nsearchives.nseindia.com"
            or not parsed.path.endswith(".xml")
        ):
            continue

        try:
            date = datetime.strptime(
                date_text, "%d-%b-%Y"
            ).date().isoformat()
        except ValueError:
            continue

        key = (company, date, url)

        if key in seen:
            continue

        seen.add(key)

        results.append({
            "company": company,
            "as_of_date": date,
            "xbrl_url": url
        })

output = ROOT / "nse_discovered_filings.csv"

with output.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["company", "as_of_date", "xbrl_url"]
    )
    writer.writeheader()
    writer.writerows(results)

print(f"Source: {source.name}")
print(f"Found {len(results)} official XML filing links")
print(f"Saved: {output.name}")
