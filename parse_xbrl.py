
"""Parse locally uploaded NSE XBRL shareholding filings."""

import csv
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "shareholding_history.csv"
FACT = "ShareholdingAsAPercentageOfTotalNumberOfShares"

CATEGORIES = {
    "mf_pct": "MutualFundsOrUTI_ContextI",
    "dii_pct": "InstitutionsDomestic_ContextI",
    "fpi_cat1": "InstitutionsForeignPortfolioInvestorCategoryOne_ContextI",
    "fpi_cat2": "InstitutionsForeignPortfolioInvestorCategoryTwo_ContextI",
}


def load_mapping():
    mapping = {}

    for filename in [
        "nse_xbrl_manifest.csv",
        "nifty200_matched_filings.csv",
    ]:
        path = ROOT / filename
        if not path.exists():
            continue

        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                url = row["xbrl_url"].strip()
                symbol = row["symbol"].strip().upper()
                date = row["as_of_date"].strip()
                parsed = urlparse(url)

                if (
                    parsed.scheme != "https"
                    or parsed.hostname != "nsearchives.nseindia.com"
                ):
                    raise ValueError(f"Untrusted URL: {url}")

                xml_name = Path(parsed.path).name
                if not xml_name.startswith("SHP_") or not xml_name.endswith("_WEB.xml"):
                    raise ValueError(f"Unexpected XML filename: {xml_name}")

                record = (symbol, date, url)

                if xml_name in mapping and mapping[xml_name] != record:
                    raise ValueError(f"Conflicting mapping: {xml_name}")

                mapping[xml_name] = record

    return mapping


def parse_file(path, mapping):
    if path.name not in mapping:
        raise ValueError(f"Unrecognized filing: {path.name}")

    symbol, expected_date, source_url = mapping[path.name]
    root = ET.parse(path).getroot()

    contexts = {}
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "context" and el.get("id"):
            instant = next(
                (
                    node.text
                    for node in el.iter()
                    if node.tag.rsplit("}", 1)[-1] == "instant"
                ),
                None,
            )
            contexts[el.get("id")] = instant

    values = {}
    for el in root.iter():
        if (
            el.tag.rsplit("}", 1)[-1] == FACT
            and el.get("contextRef") in CATEGORIES.values()
        ):
            values[el.get("contextRef")] = float(el.text) * 100

    if any(context not in values for context in CATEGORIES.values()):
        raise ValueError(f"Missing ownership facts: {path.name}")

    dates = {contexts.get(context) for context in CATEGORIES.values()}
    if dates != {expected_date}:
        raise ValueError(
            f"{path.name}: XML dates {dates} do not match {expected_date}"
        )

    return {
        "symbol": symbol,
        "as_of_date": expected_date,
        "fpi_pct": round(
            values[CATEGORIES["fpi_cat1"]]
            + values[CATEGORIES["fpi_cat2"]], 4
        ),
        "dii_pct": round(values[CATEGORIES["dii_pct"]], 4),
        "mf_pct": round(values[CATEGORIES["mf_pct"]], 4),
        "source_url": source_url,
    }


def main():
    mapping = load_mapping()
    files = sorted(ROOT.glob("SHP_*_WEB.xml"))

    if not files:
        raise SystemExit("No local NSE XML files found.")

    rows = [parse_file(path, mapping) for path in files]
    keys = [(row["symbol"], row["as_of_date"]) for row in rows]

    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate stock and reporting date.")

    rows.sort(key=lambda row: (row["symbol"], row["as_of_date"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "symbol", "as_of_date", "fpi_pct",
                "dii_pct", "mf_pct", "source_url"
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Processed {len(rows)} verified XML filings")
    print(f"Stocks covered: {len(set(row['symbol'] for row in rows))}")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
