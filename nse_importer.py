"""NSE quarterly shareholding importer: audited CSV consolidation.

Input: CSVs manually exported/transcribed from NSE's *detailed* shareholding
pattern, with explicit FPI/DII/MF categories. The NSE headline listing's
promoter/public percentages are NOT sufficient to calculate FPI/DII.
No scraping or inferred ownership figures.
"""
import argparse
import csv
import datetime as dt
import pathlib
from urllib.parse import urlparse

COLUMNS = ("symbol","as_of_date","fpi_pct","dii_pct","mf_pct","source_url")
def validate_row(row):
    symbol = (row.get("symbol") or "").strip().upper().replace(".NS","")
    if not symbol or not symbol.replace("-","").replace("&","").isalnum():
        raise ValueError("Invalid symbol")
    date = dt.date.fromisoformat((row.get("as_of_date") or "").strip())
    if date > dt.date.today():
        raise ValueError("Future reporting date")
    url = (row.get("source_url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Missing HTTPS filing source")
    values = {}
    for field in ("fpi_pct","dii_pct","mf_pct"):
        raw = (row.get(field) or "").strip()
        if raw:
            number = float(raw)
            if not 0 <= number <= 100:
                raise ValueError(f"{field} outside 0–100")
            values[field] = str(number)
        else:
            values[field] = ""
    if not any(values.values()):
        raise ValueError("No institutional percentage supplied")
    return {"symbol":symbol,"as_of_date":date.isoformat(),**values,"source_url":url}

def consolidate(source_dir, destination):
    source_dir = pathlib.Path(source_dir)
    files = sorted(source_dir.glob("*.csv"))
    if not files:
        raise ValueError("No CSV disclosure files found")
    records = {}
    for file in files:
        with file.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or any(c not in reader.fieldnames for c in COLUMNS):
                raise ValueError(f"{file.name}: missing required columns")
            for line, row in enumerate(reader, start=2):
                try:
                    parsed = validate_row(row)
                except Exception as exc:
                    raise ValueError(f"{file.name}:{line}: {exc}") from exc
                key = (parsed["symbol"],parsed["as_of_date"])
                if key in records and records[key] != parsed:
                    raise ValueError(f"Conflicting filings for {key}; resolve revisions manually")
                records[key] = parsed
    destination = pathlib.Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records[key] for key in sorted(records))
    return len(records)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate and combine detailed NSE shareholding CSVs")
    parser.add_argument("--input",default="nse_disclosures")
    parser.add_argument("--output",default="data/shareholding_history.csv")
    args = parser.parse_args()
    print(f"Validated {consolidate(args.input,args.output)} disclosure observations")
