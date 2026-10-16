"""Convert locally uploaded NSE shareholding XBRL XML into app-ready quarterly CSV.
Run: python parse_xbrl.py
"""
import csv
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / 'shareholding_history.csv'
MAPPING_FILE = ROOT / 'nse_xbrl_manifest.csv'
FACT = 'ShareholdingAsAPercentageOfTotalNumberOfShares'
CATEGORIES = {
    'mf_pct': 'MutualFundsOrUTI_ContextI',
    'dii_pct': 'InstitutionsDomestic_ContextI',
    'fpi_cat1': 'InstitutionsForeignPortfolioInvestorCategoryOne_ContextI',
    'fpi_cat2': 'InstitutionsForeignPortfolioInvestorCategoryTwo_ContextI',
}

def parse_file(path):
    tree = ET.parse(path)
    root = tree.getroot()
    contexts = {}
    for el in root.iter():
        if el.tag.rsplit('}', 1)[-1] == 'context' and el.get('id'):
            instant = next((node.text for node in el.iter() if node.tag.rsplit('}', 1)[-1] == 'instant'), None)
            contexts[el.get('id')] = instant
    values = {}
    for el in root.iter():
        if el.tag.rsplit('}', 1)[-1] == FACT and el.get('contextRef') in CATEGORIES.values():
            values[el.get('contextRef')] = float(el.text) * 100
    mf = values.get(CATEGORIES['mf_pct'])
    domestic = values.get(CATEGORIES['dii_pct'])
    fpi1 = values.get(CATEGORIES['fpi_cat1'])
    fpi2 = values.get(CATEGORIES['fpi_cat2'])
    if mf is None or domestic is None or fpi1 is None or fpi2 is None:
        raise ValueError(f'{path.name}: missing required aggregate ownership facts: {values}')
    dates = {contexts.get(k) for k in CATEGORIES.values()}
    if len(dates) != 1 or None in dates:
        raise ValueError(f'{path.name}: missing or conflicting reporting dates: {dates}')
    date = dates.pop()
    with MAPPING_FILE.open(newline='', encoding='utf-8-sig') as f:
        FILE_SYMBOLS = {
            row['filename'].strip(): row['symbol'].strip().upper()
            for row in csv.DictReader(f)
        }

    symbol = FILE_SYMBOLS.get(path.name)

    if symbol is None:
        raise ValueError(
            f'Unknown company for {path.name}. '
            'Add a verified filename-to-symbol mapping first.'
        )
    return {'symbol':symbol, 'as_of_date':date, 'fpi_pct':round(fpi1+fpi2, 4),
            'dii_pct':round(domestic, 4), 'mf_pct':round(mf, 4),
            'source_url':f'https://nsearchives.nseindia.com/corporate/xbrl/{path.name}'}

def main():
    files = sorted(ROOT.glob('SHP_*_WEB.xml'))
    if not files:
        raise SystemExit('No SHP_*_WEB.xml files found alongside this script.')
    rows = [parse_file(p) for p in files]
    rows.sort(key=lambda x: x['as_of_date'])
    if len({(r['symbol'],r['as_of_date']) for r in rows}) != len(rows):
        raise ValueError('Duplicate quarter detected')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['symbol','as_of_date','fpi_pct','dii_pct','mf_pct','source_url'])
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(f"{row['as_of_date']}: MF {row['mf_pct']:.2f}%, Domestic institutions {row['dii_pct']:.2f}%, FPI {row['fpi_pct']:.2f}%")
    print(f'Saved {OUT}')

if __name__ == '__main__':
    main()
