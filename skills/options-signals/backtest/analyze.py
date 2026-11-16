#!/usr/bin/env python3
"""Pick configs on TRAIN only (both tickers), then report their untouched TEST results."""
import json, sys
import numpy as np

res = json.load(open(sys.argv[1]))
def short(c):
    return (f"{'+'.join(c['triggers']):13} confirm={'Y' if c['confirm'] else 'N'} win={c['start']}-{c['end']} "
            f"stop={int(c['stop']*100)}% tgt={int(c['target']*100)}% tstop={c['time_stop']}m opp={'Y' if c['opp'] else 'N'} max/day={c['max_trades']}")

for r in res:
    tr = [r[t]['train'] for t in ('SPY', 'QQQ')]
    r['score'] = min(x['t'] for x in tr) if all(x['n'] >= 100 for x in tr) else -99
n = len(res)
print(f'{n} configs tested')
for split in ('train', 'test'):
    both = sum(all(r[t][split]['total'] > 0 for t in ('SPY', 'QQQ')) for r in res)
    print(f'  profitable on BOTH tickers in {split}: {both} ({both / n:.1%})')
tr_t = np.array([min(r[t]['train']['t'] for t in ('SPY', 'QQQ')) for r in res])
te_t = np.array([min(r[t]['test']['t'] for t in ('SPY', 'QQQ')) for r in res])
print(f'  rank correlation train->test (min t-stat): {np.corrcoef(tr_t.argsort().argsort(), te_t.argsort().argsort())[0,1]:.2f}')

top = sorted(res, key=lambda r: -r['score'])[:10]
print('\nTop 10 chosen on TRAIN (Nov 2024 - Dec 2025), then TEST (Jan - Nov 2026), 1 contract per trade:')
for k, r in enumerate(top, 1):
    print(f"\n#{k} {short(r['cfg'])}")
    for t in ('SPY', 'QQQ'):
        a, b = r[t]['train'], r[t]['test']
        print(f"   {t} train: n={a['n']:5} total=${a['total']:>8,.0f} win={a['win']:.0%} pf={a['pf']:.2f} t={a['t']:5.2f} | "
              f"TEST: n={b['n']:5} total=${b['total']:>8,.0f} win={b['win']:.0%} pf={b['pf']:.2f} t={b['t']:5.2f} months+={b['months_pos']:.0%} maxDD=${b['mdd']:,.0f}")
