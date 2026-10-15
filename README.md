# NSE 200 Institutional Accumulation Research Screener

A local Streamlit research dashboard for a **1–3 month watchlist**. It uses official Nifty 200 constituents, Yahoo Finance daily market data, and **user-supplied verified** ownership disclosures. It does not invent FPI, DII, or mutual fund ownership figures.

## Run

Install Python 3.10+ and in the extracted folder run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The browser will open the dashboard. Click **Run screening**.

## Data sources

- Official Nifty 200 constituents: https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv
- NSE company quarterly shareholding: https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern
- AMFI/AMC monthly portfolio disclosures: https://www.amfiindia.com/
- Market data: Yahoo Finance via `yfinance` (unofficial; may fail, be delayed or incomplete).

## Upload files

`shareholding_template.csv`: `symbol,as_of_date,fpi_pct,dii_pct,mf_pct,source_url`

`mf_holdings_template.csv`: `symbol,as_of_date,mf_schemes_holding,mf_shares_held,source_url`

Add at least two observations for each stock. Dates must be `YYYY-MM-DD`. Percentages are ownership shares (e.g., `14.5` means 14.5%, not `0.145`). FPI and DII definitions must be consistent between dates. MF ownership is typically a subset of DII ownership; do not add them together as though independent. If the same exposure is represented by both MF quarterly ownership and MF monthly holdings, the model may double-weight it: treat the model as exploratory and consider using one MF signal only.

Monthly mutual fund share counts require consistent scheme aggregation and corporate action adjustments. A rise in shares held can reflect transactions, fund flows, or corporate actions; validate before concluding accumulation.

## Scoring (90-point exploratory model)

- FPI holding change: up to 12 points
- DII holding change: up to 12 points
- MF holding change: up to 11 points
- Monthly MF holdings change: up to 15 points
- Relative strength vs benchmark: up to 20 points
- Price trend: up to 10 points
- Relative daily volume: up to 10 points

**Important:** This is an *evidence-coverage-sensitive score*, not a predictive probability. Missing ownership values earn zero points but are separately flagged as missing; this penalizes incomplete coverage. By default, the dashboard hides stocks without verified ownership changes. The volume component is **not** delivery data, and the model has no direct earnings/valuation data. Scores are not cross-sectionally calibrated and must not be treated as investment recommendations.

## Limitations

- It does not auto-download company-level institutional holdings from NSE or all AMC portfolio files; those sources have heterogeneous layouts and need validation.
- NSE constituents change over time; the screener uses the current membership and therefore cannot perform survivorship-bias-free historical backtesting.
- The benchmark ticker `^CNX200` might not be served by Yahoo Finance; change it explicitly in the sidebar if unavailable. No silent benchmark replacement.
- Quarterly holdings lag real trading; no method can know the next 1–3 months of institutional buying from public data.
- A positive score does not imply a profitable trade or forecast.
