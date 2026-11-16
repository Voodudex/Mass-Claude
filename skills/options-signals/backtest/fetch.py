#!/usr/bin/env python3
"""Download 1-minute bars from Polygon (key injected by the network proxy) to CSV, US/Eastern timestamps."""
import csv, json, sys, time
from datetime import datetime
from urllib.request import urlopen
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
ticker, start, end, out = sys.argv[1:5]
url = (f'https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/{start}/{end}'
       '?adjusted=true&sort=asc&limit=50000')
rows = 0
with open(out, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    while url:
        for attempt in range(6):
            try:
                data = json.load(urlopen(url, timeout=60))
                break
            except HTTPError as e:
                if e.code != 429:
                    raise
                time.sleep(15)
        for b in data.get('results', []):
            ts = datetime.fromtimestamp(b['t'] / 1000, ET).replace(tzinfo=None)
            w.writerow([ts.isoformat(sep=' '), b['o'], b['h'], b['l'], b['c'], b['v']])
            rows += 1
        url = data.get('next_url')
        print(f'{ticker}: {rows} bars, last {ts}', flush=True)
        if url:
            time.sleep(12.5)  # free tier: 5 requests/minute
print(f'{ticker} done: {rows} bars')
