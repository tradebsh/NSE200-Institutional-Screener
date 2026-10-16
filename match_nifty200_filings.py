
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def normalize(name):
    name = name.upper().replace("&", " AND ")
    name = re.sub(r"[^A-Z0-9]+", " ", name)
    words = name.split()

    while words and words[-1] in {
        "LIMITED", "LTD"
    }:
        words.pop()

    return " ".join(words)


with (ROOT / "ind_nifty200list.csv").open(
    encoding="utf-8-sig", newline=""
) as f:
    constituents = list(csv.DictReader(f))

with (ROOT / "nse_discovered_filings.csv").open(
    encoding="utf-8-sig", newline=""
) as f:
    filings = list(csv.DictReader(f))

lookup = {}
ambiguous = set()

for stock in constituents:
    key = normalize(stock["Company Name"])
    if key in lookup:
        ambiguous.add(key)
    else:
        lookup[key] = stock["Symbol"].strip().upper()

for key in ambiguous:
    lookup.pop(key, None)

matches = []
unmatched = set()

for filing in filings:
    key = normalize(filing["company"])
    symbol = lookup.get(key)

    if not symbol:
        unmatched.add(filing["company"])
        continue

    matches.append({
        "symbol": symbol,
        "as_of_date": filing["as_of_date"],
        "xbrl_url": filing["xbrl_url"]
    })

output = ROOT / "nifty200_matched_filings.csv"

with output.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["symbol", "as_of_date", "xbrl_url"]
    )
    writer.writeheader()
    writer.writerows(matches)

print(f"Nifty 200 constituents: {len(constituents)}")
print(f"Discovered filings: {len(filings)}")
print(f"Matched filings: {len(matches)}")
print(f"Stocks with matches: {len(set(x['symbol'] for x in matches))}")
print(f"Unmatched company names: {len(unmatched)}")
print(f"Saved: {output.name}")
