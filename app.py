import io
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title='NSE 200 Institutional Accumulation', page_icon='📈', layout='wide')
st.title('NSE 200 | Institutional Accumulation Research Screener')
st.caption('1–3 month research watchlist • Ownership evidence + price confirmation • Not a prediction or trading signal')

CONSTITUENTS_URL = 'https://niftyindices.com/IndexConstituent/ind_nifty200list.csv'
DATA_DIR = Path(__file__).resolve().parent / 'data'

@st.cache_data(ttl=3600, show_spinner=False)
def read_repository_csv(filename):
    path = DATA_DIR / filename
    return path.read_bytes() if path.is_file() else None

OWNERSHIP_COLS = ['symbol','as_of_date','fpi_pct','dii_pct','mf_pct','source_url']
MF_COLS = ['symbol','as_of_date','mf_schemes_holding','mf_shares_held','source_url']

@st.cache_data(ttl=86400, show_spinner=False)
def get_constituents():
    r = requests.get(CONSTITUENTS_URL, headers={'User-Agent':'Mozilla/5.0'}, timeout=25)
    r.raise_for_status()
    frame = pd.read_csv(io.BytesIO(r.content))
    names = {c.lower().strip(): c for c in frame.columns}
    sym_col = names.get('symbol')
    if not sym_col:
        raise ValueError('Constituent file has no Symbol column.')
    syms = frame[sym_col].dropna().astype(str).str.strip().str.upper().unique().tolist()
    if len(syms) < 150:
        raise ValueError('Constituent file unexpectedly small; check source.')
    return syms, frame

@st.cache_data(ttl=3600, show_spinner=False)
def get_prices(symbols, period='1y'):
    tickers = [f'{s}.NS' for s in symbols]
    raw = yf.download(tickers, period=period, interval='1d', auto_adjust=True, group_by='ticker', progress=False, threads=True)
    output = {}
    for sym, ticker in zip(symbols, tickers):
        try:
            data = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) else raw
            close = pd.to_numeric(data['Close'], errors='coerce').dropna()
            volume = pd.to_numeric(data['Volume'], errors='coerce').reindex(close.index)
            if len(close) >= 75:
                output[sym] = pd.DataFrame({'close': close, 'volume': volume})
        except (KeyError, TypeError, ValueError):
            continue
    return output

def validate_upload(upload, columns, label):
    if upload is None:
        return None
    df = pd.read_csv(upload, dtype={'symbol':str,'as_of_date':str,'source_url':str})
    missing = set(columns) - set(df.columns)
    if missing:
        st.error(f'{label}: missing columns {sorted(missing)}')
        return None
    df = df[columns].copy()
    df['symbol'] = df['symbol'].astype(str).str.strip().str.upper().str.replace('.NS','',regex=False)
    df['as_of_date'] = pd.to_datetime(df['as_of_date'], errors='coerce')
    for c in columns:
        if c not in ('symbol','as_of_date','source_url'):
            df[c] = pd.to_numeric(df[c], errors='coerce')
    if df['as_of_date'].isna().any():
        st.error(f'{label}: invalid as_of_date values; use YYYY-MM-DD.')
        return None
    if df.duplicated(['symbol','as_of_date']).any():
        st.error(f'{label}: duplicate symbol + as_of_date rows.')
        return None
    if (df['as_of_date'] > pd.Timestamp.today().normalize()).any():
        st.error(f'{label}: future-dated records detected.')
        return None
    if label == 'Shareholding':
        pct = df[['fpi_pct','dii_pct','mf_pct']]
        if ((pct < 0) | (pct > 100)).any().any():
            st.error('Shareholding percentages must be between 0 and 100.')
            return None
    return df.sort_values('as_of_date')

def latest_deltas(df, cols):
    if df is None:
        return {}
    result = {}
    for symbol, group in df.groupby('symbol'):
        group = group.sort_values('as_of_date')
        if len(group) < 2:
            continue
        last, previous = group.iloc[-1], group.iloc[-2]
        item = {'date':last['as_of_date'].date().isoformat(), 'previous_date':previous['as_of_date'].date().isoformat(), 'source_url':last['source_url']}
        for col in cols:
            if pd.notna(last[col]) and pd.notna(previous[col]):
                item[col+'_delta'] = float(last[col] - previous[col])
        result[symbol] = item
    return result

def scaled_score(value, low, high):
    return float(np.clip((value-low)/(high-low),0,1))

with st.sidebar:
    st.header('Data inputs')
    uploaded_constituents = st.file_uploader('Optional NSE 200 constituent CSV override', type='csv', key='const')
    ownership_upload = st.file_uploader('Quarterly shareholding history CSV', type='csv', key='own')
    mf_upload = st.file_uploader('Monthly MF holdings history CSV', type='csv', key='mf')
    st.caption('Each institutional file needs at least two dated observations per stock. Source URLs are retained for audit.')
    benchmark = st.text_input('Benchmark ticker (Yahoo Finance)', '^CNX200')
    max_symbols = st.slider('Stocks to scan (200 = full universe)', 20, 200, 200, step=10)
    min_score = st.slider('Minimum evidence-adjusted score', 0, 100, 20, help='Without ownership uploads, PRICE ONLY stocks can score at most 44.4% of the 90-point model.')
    st.divider()
    st.markdown('[Official Nifty 200 constituents](https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv)')
    st.markdown('[NSE company shareholding filings](https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern)')
    st.markdown('[AMFI disclosures](https://www.amfiindia.com/)')

ownership_source = ownership_upload if ownership_upload is not None else read_repository_csv('shareholding_history.csv')
mf_source = mf_upload if mf_upload is not None else read_repository_csv('mf_holdings_history.csv')
ownership = validate_upload(io.BytesIO(ownership_source) if isinstance(ownership_source, bytes) else ownership_source, OWNERSHIP_COLS, 'Shareholding')
mf_data = validate_upload(io.BytesIO(mf_source) if isinstance(mf_source, bytes) else mf_source, MF_COLS, 'MF holdings')
if ownership_upload is None and ownership is not None:
    st.success('Quarterly institutional history loaded automatically from repository.')
if mf_upload is None and mf_data is not None:
    st.success('Monthly mutual fund history loaded automatically from repository.')
if ownership is None and mf_data is None:
    st.caption('No verified institutional datasets yet. Rankings remain PRICE ONLY.')

with st.expander('CSV formats and interpretation', expanded=False):
    st.code('symbol,as_of_date,fpi_pct,dii_pct,mf_pct,source_url\nRELIANCE,2026-06-30,,,,https://example.org/source\nRELIANCE,2026-09-30,,,,https://example.org/source', language='csv')
    st.code('symbol,as_of_date,mf_schemes_holding,mf_shares_held,source_url\nRELIANCE,2026-08-31,,,https://example.org/source\nRELIANCE,2026-09-30,,,https://example.org/source', language='csv')
    st.warning('Example rows contain blank values intentionally. Enter verified data only. MF share counts should be aggregated consistently across schemes and adjusted for corporate actions. MF percentage is often a subset of DII percentage: never sum them as separate ownership percentages.')

if uploaded_constituents is not None:
    cdf = pd.read_csv(uploaded_constituents)
    symcol = next((c for c in cdf.columns if c.lower().strip() == 'symbol'), None)
    if not symcol:
        st.error('Uploaded constituent CSV must include Symbol column.')
        st.stop()
    symbols = cdf[symcol].dropna().astype(str).str.strip().str.upper().tolist()
    st.info('Using user-uploaded universe. Verify that it is the current Nifty 200 list.')
else:
    try:
        symbols, _ = get_constituents()
    except Exception as e:
        st.error(f'Could not load official NSE 200 constituents: {e}. Upload the official CSV in the sidebar.')
        st.stop()

symbols = list(dict.fromkeys(symbols))[:max_symbols]
if len(symbols) < 1:
    st.stop()

st.info(f'Universe: {len(symbols)} symbols. Ownership: {"loaded" if ownership is not None else "not supplied"}. MF monthly data: {"loaded" if mf_data is not None else "not supplied"}.')

if 'screening_started' not in st.session_state:
    st.session_state.screening_started = False

if st.button('Run screening', type='primary'):
    st.session_state.screening_started = True

if not st.session_state.screening_started:
    st.stop()

with st.spinner('Fetching historical prices and evaluating available evidence...'):
    prices = get_prices(symbols)
    try:
        benchmark_df = yf.download(benchmark.strip(), period='1y', interval='1d', auto_adjust=True, progress=False)
        bench_close = benchmark_df['Close']
        if isinstance(bench_close, pd.DataFrame):
            bench_close = bench_close.iloc[:,0]
        bench_close = pd.to_numeric(bench_close,errors='coerce').dropna()
        if len(bench_close) < 75:
            raise ValueError('Insufficient benchmark history')
    except Exception as e:
        st.error(f'Benchmark {benchmark!r} could not be downloaded: {e}. Set a working benchmark symbol and rerun. No silent substitution is made.')
        st.stop()

own_deltas = latest_deltas(ownership, ['fpi_pct','dii_pct','mf_pct'])
mf_deltas = latest_deltas(mf_data, ['mf_schemes_holding','mf_shares_held'])

records = []
for symbol, p in prices.items():
    close, vol = p['close'], p['volume']
    b = bench_close.reindex(close.index, method='ffill').dropna()
    c = close.reindex(b.index).dropna()
    if len(c) < 75 or len(b) < 75:
        continue
    n = min(len(c),len(b))
    c,b = c.iloc[-n:],b.iloc[-n:]
    if len(c)<65:
        continue
    r1 = float(c.iloc[-1]/c.iloc[-22]-1) if len(c)>22 else np.nan
    r3 = float(c.iloc[-1]/c.iloc[-64]-1) if len(c)>64 else np.nan
    br1 = float(b.iloc[-1]/b.iloc[-22]-1) if len(b)>22 else np.nan
    br3 = float(b.iloc[-1]/b.iloc[-64]-1) if len(b)>64 else np.nan
    rs1,rs3 = (r1-br1)*100,(r3-br3)*100
    ma50 = float(c.rolling(50).mean().iloc[-1])
    ma200 = float(c.rolling(200).mean().iloc[-1]) if len(c)>=200 else np.nan
    trend = bool(c.iloc[-1] > ma50 and (np.isnan(ma200) or c.iloc[-1] > ma200))
    vol_avg = vol.rolling(20).mean()
    relvol = float(vol.iloc[-1]/vol_avg.iloc[-1]) if vol_avg.iloc[-1]>0 else np.nan
    # Price-confirmation component (max 30). This is not institutional evidence.
    price_score = 20*(0.5*scaled_score(rs1,-5,10)+0.5*scaled_score(rs3,-10,20))
    trend_score = 10 if trend else 0
    own = own_deltas.get(symbol,{})
    fpi_change = own.get('fpi_pct_delta', np.nan)
    dii_change = own.get('dii_pct_delta', np.nan)

    
    if pd.notna(fpi_change) and pd.notna(dii_change):
        if fpi_change > 0 and dii_change > 0:
            ownership_signal = 'BOTH INCREASING'
        elif fpi_change < 0 and dii_change < 0:
            ownership_signal = 'BOTH DECREASING'
        elif fpi_change == 0 and dii_change == 0:
            ownership_signal = 'UNCHANGED'
        elif fpi_change >= 0 and dii_change >= 0:
            ownership_signal = 'PARTIAL INCREASE'
        elif fpi_change <= 0 and dii_change <= 0:
            ownership_signal = 'PARTIAL DECREASE'
        else:
            ownership_signal = 'MIXED'
    else:
        ownership_signal = 'INSUFFICIENT DATA'
    mfd = mf_deltas.get(symbol,{})
    
        conviction_coverage = sum(
        pd.notna(value)
        for value in [
            fpi_change,
            dii_change,
            own.get('mf_pct_delta', np.nan)
        ]
        )
    # Institutional Conviction Score (0-100)
    conviction_score = 0

    if pd.notna(fpi_change) and fpi_change > 0:
        conviction_score += 30

    if pd.notna(dii_change) and dii_change > 0:
        conviction_score += 30

    mf_change = own.get('mf_pct_delta', np.nan)
    if pd.notna(mf_change) and mf_change > 0:
        conviction_score += 20

    if rs3 > 0:
        conviction_score += 10

    if trend:
        conviction_score += 10
    # Ownership 35 pts: FPI 12, DII 12, MF 11. Only independently verified deltas count.
    # Missing data receives no points AND is excluded from coverage denominator.
    components = [('FPI',12,'fpi_pct_delta',own),('DII',12,'dii_pct_delta',own),('MF',11,'mf_pct_delta',own)]
    earned, possible = 0.0,0.0
    for _,weight,key,source in components:
        if key in source:
            possible += weight
            earned += weight*scaled_score(source[key],-0.25,0.75)
    # Monthly MF holdings: 15 points; either shares held or scheme count, not both.
    mf_key = 'mf_shares_held_delta' if 'mf_shares_held_delta' in mfd else 'mf_schemes_holding_delta'
    if mf_key in mfd:
        possible += 15
        delta = mfd[mf_key]
        earned += 15 if delta>0 else 7.5 if delta==0 else 0
    # Volume is only corroboration, max 10 pts, not proof of delivery or accumulation.
    volume_score = 10*scaled_score(relvol,0.7,2.0) if np.isfinite(relvol) else 0
    total = round(price_score+trend_score+volume_score+earned,1)
    # Max possible is 30 market + 10 volume + 50 ownership.
    coverage = round(possible/50*100)
    evidence_status = 'OWNERSHIP CONFIRMED' if coverage>=70 else 'PARTIAL OWNERSHIP' if coverage>0 else 'PRICE ONLY'
    records.append({'Symbol':symbol,'Evidence score / 90':total,'Ownership coverage %':coverage,'Evidence':evidence_status,'Institutional Signal':ownership_signal,
                    'Institutional Conviction Score':conviction_score,
                    'Institutional Data Fields Available':conviction_coverage,
        'FPI change (pp)':own.get('fpi_pct_delta',np.nan),'DII change (pp)':own.get('dii_pct_delta',np.nan),
        'MF ownership change (pp)':own.get('mf_pct_delta',np.nan),'MF shares change':mfd.get('mf_shares_held_delta',np.nan),
        'MF schemes change':mfd.get('mf_schemes_holding_delta',np.nan),'RS 1M (pp)':round(rs1,2),'RS 3M (pp)':round(rs3,2),
        'Rel volume':round(relvol,2) if np.isfinite(relvol) else np.nan,'Trend positive':trend,
        'Ownership as of':own.get('date',''),'MF data as of':mfd.get('date',''),
        'Ownership source':own.get('source_url',''),'MF source':mfd.get('source_url',''),
        'Price as of':str(c.index[-1].date())})

if not records:
    st.error('No price series had sufficient history. Check Yahoo Finance access or try again later.')
    st.stop()

result = pd.DataFrame(records)
# Score is explicitly /90: 35 quarterly ownership + 15 monthly MF + 20 RS + 10 trend + 10 volume.
result = result.sort_values(
    ['Institutional Conviction Score', 'Ownership coverage %', 'Evidence score / 90'],
    ascending=False
)
max_score = 90
result['Score % of available model max'] = (result['Evidence score / 90']/max_score*100).round(1)
filtered = result[(result['Score % of available model max']>=min_score)]

st.warning('Scores are exploratory and NOT validated forecasts. Missing institutional data is never imputed. PRICE ONLY rows must not be called institutional accumulation. Relative volume is not delivery percentage.')
cols = st.columns(4)
cols[0].metric('Stocks with prices',len(result))
cols[1].metric('Verified ownership coverage',int((result['Ownership coverage %']>0).sum()))
cols[2].metric('Passing score filter',len(filtered))
cols[3].metric('Benchmark',benchmark)

st.subheader('Ranked watchlist')
require_evidence = st.checkbox('Show only stocks with verified institutional ownership data', value=False, help='Turn on after uploading verified ownership history.')
both_increasing_only = st.checkbox(
    'Show only stocks where FPI and DII ownership both increased',
    value=False
)
view = filtered[filtered['Ownership coverage %']>0] if require_evidence else filtered
if both_increasing_only:
    view = view[view['Institutional Signal'] == 'BOTH INCREASING']
if view.empty:
    st.info('No stocks meet the current filters. Try lowering the minimum score in the sidebar. Verified institutional rankings require dated ownership disclosures.')
else:
    st.dataframe(view, use_container_width=True, hide_index=True)

st.download_button('Download full ranked CSV',data=result.to_csv(index=False).encode('utf-8'),file_name='nse200_research_rankings.csv',mime='text/csv')
st.caption('FPI/DII/MF quarterly percentages are changes in percentage points, not estimated net purchases. Price return uses ~21/63 sessions. Coverage measures available ownership fields, not data reliability.')
