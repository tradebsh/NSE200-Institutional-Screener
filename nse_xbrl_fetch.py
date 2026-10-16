"""Download explicitly listed official NSE XBRL files for review, never infer holdings."""
import argparse, csv, hashlib, json, pathlib, time
from urllib.parse import urlparse
import requests


ALLOWED_HOSTS = {
    'nseindia.com',
    'www.nseindia.com',
    'nseindia.in',
    'www.nseindia.in',
    'archives.nseindia.com',
    'nsearchives.nseindia.com',
}
MAX_BYTES = 12_000_000

def allowed_url(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname in ALLOWED_HOSTS and not parsed.username and not parsed.password

def run(manifest, output):
    output = pathlib.Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(pathlib.Path(manifest).open(encoding='utf-8-sig', newline='')))
    if not rows:
        print('No approved XBRL URLs in manifest. Nothing downloaded.')
        return 0
    if len(rows)>250:
        raise ValueError('Limit manifest to 250 files per run')
    session = requests.Session()
    session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; ResearchDisclosureFetcher/1.0)', 'Accept':'application/xml,text/xml,application/octet-stream,*/*'})
    
    saved=[]
    for i, row in enumerate(rows):
        url=(row.get('xbrl_url') or '').strip()
        symbol=(row.get('symbol') or '').strip().upper()
        date=(row.get('as_of_date') or '').strip()
        if not allowed_url(url):
            raise ValueError(f'Row {i+2}: URL must be an official NSE HTTPS host')
        import datetime
        datetime.date.fromisoformat(date)
        if not symbol or not all(c.isalnum() or c in '-&' for c in symbol):
            raise ValueError(f'Row {i+2}: invalid symbol')
        response=session.get(url,timeout=35,stream=True,allow_redirects=False)
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError(f'Row {i+2}: redirect rejected; verify official URL')
        chunks=[]; total=0
        for chunk in response.iter_content(chunk_size=65536):
            total+=len(chunk)
            if total>MAX_BYTES: raise ValueError('Disclosure exceeds size limit')
            chunks.append(chunk)
        data=b''.join(chunks)
        if not data: raise ValueError('Empty download')
        digest=hashlib.sha256(data).hexdigest()
        suffix=pathlib.PurePosixPath(urlparse(url).path).suffix.lower()
        if suffix not in ('.xml','.xbrl','.zip'):
            suffix='.bin'
        filename=f'{symbol}_{date}_{digest[:12]}{suffix}'
        (output/filename).write_bytes(data)
        saved.append({'symbol':symbol,'as_of_date':date,'source_url':url,'filename':filename,'sha256':digest,'bytes':len(data)})
        time.sleep(1)
    (output/'download_audit.json').write_text(json.dumps(saved,indent=2))
    print(f'Downloaded {len(saved)} documents for manual taxonomy review. No ownership figures generated.')
    return len(saved)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',default='nse_xbrl_manifest.csv')
    p.add_argument('--output',default='downloaded_disclosures')
    args=p.parse_args()
    run(args.manifest,args.output)
