#!/usr/bin/env python3
"""Backtest the VWAP / 50 EMA / opening-range options strategy on 1-minute SPY & QQQ bars.

Option model: 0DTE, strike = nearest $1 to entry price (+offset OTM), Black-Scholes (r=0)
with IV = 1.2 x trailing 10-day realized vol (past data only). Costs per side: $0.02/share
spread+slippage and $0.65/contract commission. Entry at the next bar's open after a signal close.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
import os
from multiprocessing import Pool

import numpy as np
import pandas as pd

DATA = os.environ.get('BT_DATA', 'data')  # folder holding SPY.csv and QQQ.csv from fetch.py
SPLIT = pd.Timestamp('2026-01-01')
COST_PER_SIDE = 0.02      # $ per share-equivalent (spread + slippage)
COMMISSION = 0.65         # $ per contract per side
YEAR_MIN = 252 * 390


def prepare(ticker, ema_period=50):
    df = pd.read_csv(f'{DATA}/{ticker}.csv', parse_dates=['timestamp'])
    t = df.timestamp.dt
    minute = (t.hour * 60 + t.minute) - (9 * 60 + 30)
    df = df[(minute >= 0) & (minute < 390)].copy()
    df['minute'] = minute[df.index]
    df['date'] = df.timestamp.dt.normalize()
    # Drop half-days / broken sessions: need a bar in the first and last 30 minutes.
    g = df.groupby('date').minute
    good = (g.transform('min') <= 2) & (g.transform('max') >= 385) & (g.transform('count') >= 300)
    df = df[good].reset_index(drop=True)
    tp = (df.high + df.low + df.close) / 3
    df['vwap'] = (tp * df.volume).groupby(df.date).cumsum() / df.volume.groupby(df.date).cumsum()
    df['ema'] = df.close.ewm(span=ema_period, adjust=False).mean()
    df['ema_ready'] = np.arange(len(df)) >= ema_period
    first = df.minute < 15
    orh = df.high.where(first).groupby(df.date).transform('max')
    orl = df.low.where(first).groupby(df.date).transform('min')
    # Crosses on close vs previous close (same day only).
    same = df.date.eq(df.date.shift())
    pc = df.close.shift()
    def cross(level):
        pl = level.shift()
        up = same & (pc <= pl) & (df.close > level)
        dn = same & (pc >= pl) & (df.close < level)
        return up.astype(int) - dn.astype(int)
    df['s_vwap'] = cross(df.vwap)
    df['s_ema'] = cross(df.ema) * (df.ema_ready & df.ema_ready.shift(fill_value=False))
    above, below = (df.minute >= 15) & (df.close > orh), (df.minute >= 15) & (df.close < orl)
    first_up = above & ~above.groupby(df.date).shift(fill_value=False).groupby(df.date).cummax()
    first_dn = below & ~below.groupby(df.date).shift(fill_value=False).groupby(df.date).cummax()
    df['s_orb'] = first_up.astype(int) - first_dn.astype(int)
    # IV from the previous 10 sessions' realized 1-minute volatility.
    lr = np.log(df.close).diff().where(same)
    daily_var = (lr ** 2).groupby(df.date).sum() / df.groupby('date').size()
    rv = np.sqrt(daily_var.rolling(10).mean().shift(1) * YEAR_MIN)
    df['iv'] = df.date.map((1.2 * rv).clip(lower=0.08))
    df = df[df.iv.notna()].reset_index(drop=True)
    return df


def ncdf(x):
    return 0.5 * (1 + math.erf(x / 1.4142135623730951))


def bs(S, K, minutes_left, iv, call):
    T = max(minutes_left, 0.5) / YEAR_MIN
    v = iv * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * v * v) / v
    d2 = d1 - v
    return S * ncdf(d1) - K * ncdf(d2) if call else K * ncdf(-d2) - S * ncdf(-d1)


G = {}


def load_all():
    for tk in ('SPY', 'QQQ'):
        df = prepare(tk)
        G[tk] = {c: df[c].to_numpy() for c in ('minute', 'open', 'high', 'low', 'close', 'vwap', 'ema', 'iv', 's_vwap', 's_ema', 's_orb')}
        G[tk]['date'] = df.date.to_numpy()
        G[tk]['dayend'] = df.groupby('date').minute.transform(lambda s: s.index.max()).to_numpy()
    return G


def simulate(cfg, tk):
    d = G[tk]
    m, o, h, l, c = d['minute'], d['open'], d['high'], d['low'], d['close']
    vw, em, iv, date, dayend = d['vwap'], d['ema'], d['iv'], d['date'], d['dayend']
    sig = sum(d['s_' + t] * 1 for t in cfg['triggers']) if len(cfg['triggers']) == 1 else None
    active = [d['s_' + t] for t in cfg['triggers']]
    # Combined direction per bar: +1/-1 if all firing triggers agree, else 0.
    ups = np.zeros(len(m), bool); dns = np.zeros(len(m), bool)
    for a in active:
        ups |= a > 0; dns |= a < 0
    dirn = ups.astype(int) - dns.astype(int)
    dirn[ups & dns] = 0
    cand = np.flatnonzero(dirn)
    trades, i_next, day_count, cur_day = [], -1, 0, None
    for i in cand:
        if i < i_next or i + 1 > dayend[i]:
            continue
        if date[i] != cur_day:
            cur_day, day_count = date[i], 0
        if day_count >= cfg['max_trades']:
            continue
        e = i + 1
        if not (cfg['start'] <= m[e] <= cfg['end']):
            continue
        dr = dirn[i]
        if cfg['confirm'] and not ((c[i] > vw[i] and c[i] > em[i]) if dr > 0 else (c[i] < vw[i] and c[i] < em[i])):
            continue
        call = dr > 0
        S0 = o[e]
        K = round(S0) + (cfg['otm'] if call else -cfg['otm'])
        vol = iv[e]
        mid0 = bs(S0, K, 390 - m[e], vol, call)
        if mid0 < 0.05:
            continue
        stop_px, tgt_px = mid0 * (1 - cfg['stop']), mid0 * (1 + cfg['target'])
        exit_px, j = None, e
        for j in range(e, dayend[i] + 1):
            left = 390 - m[j] - 1
            worst = bs(l[j] if call else h[j], K, left, vol, call)
            best = bs(h[j] if call else l[j], K, left, vol, call)
            if worst <= stop_px:
                exit_px, why = stop_px, 'stop'; break
            if best >= tgt_px:
                exit_px, why = tgt_px, 'target'; break
            if cfg['opp'] and dirn[j] == -dr:
                exit_px, why = bs(c[j], K, left, vol, call), 'opposite'; break
            if m[j] - m[e] + 1 >= cfg['time_stop'] or m[j] >= 385:
                exit_px, why = bs(c[j], K, left, vol, call), 'time'; break
        if exit_px is None:
            exit_px, why = bs(c[j], K, 0.5, vol, call), 'eod'
        pnl = (max(exit_px - COST_PER_SIDE, 0) - (mid0 + COST_PER_SIDE)) * 100 - 2 * COMMISSION
        trades.append((date[i], pnl, why))
        day_count += 1
        i_next = j  # a signal on the exit bar may open the next trade
    return trades


def stats(trades):
    if not trades:
        return {'n': 0, 'total': 0.0, 'mean': 0.0, 't': 0.0, 'win': 0.0, 'pf': 0.0, 'mdd': 0.0, 'months_pos': 0.0}
    p = np.array([t[1] for t in trades])
    months = pd.Series(p, index=pd.to_datetime([t[0] for t in trades])).resample('ME').sum()
    months = months[months != 0]
    cum = np.cumsum(p)
    sd = p.std(ddof=1) if len(p) > 1 else 0
    return {'n': len(p), 'total': round(float(p.sum()), 0), 'mean': round(float(p.mean()), 2),
            't': round(float(p.mean() / sd * math.sqrt(len(p))), 2) if sd else 0.0,
            'win': round(float((p > 0).mean()), 3),
            'pf': round(float(p[p > 0].sum() / -p[p < 0].sum()), 2) if (p < 0).any() else 99.0,
            'mdd': round(float((np.maximum.accumulate(cum) - cum).max()), 0),
            'months_pos': round(float((months > 0).mean()), 2) if len(months) else 0.0}


def split(trades):
    tr = [t for t in trades if pd.Timestamp(t[0]) < SPLIT]
    te = [t for t in trades if pd.Timestamp(t[0]) >= SPLIT]
    return tr, te


def run_cfg(cfg):
    out = {'cfg': cfg}
    for tk in ('SPY', 'QQQ'):
        tr, te = split(simulate(cfg, tk))
        out[tk] = {'train': stats(tr), 'test': stats(te)}
    return out


def grid():
    trig = [list(x) for r in (1, 2, 3) for x in itertools.combinations(('vwap', 'ema', 'orb'), r)]
    keys = dict(triggers=trig, confirm=[False, True], start=[15, 30], end=[240, 330], stop=[0.25, 0.5],
                target=[0.5, 1.0], time_stop=[15, 45], opp=[True, False], max_trades=[2, 10], otm=[0])
    for combo in itertools.product(*keys.values()):
        yield dict(zip(keys, combo))


if __name__ == '__main__':
    load_all()
    mode = sys.argv[1]
    if mode == 'literal':
        cfg = dict(triggers=['vwap', 'ema', 'orb'], confirm=False, start=1, end=385, stop=1.0, target=99.0,
                   time_stop=999, opp=True, max_trades=999, otm=0)
        print(json.dumps(run_cfg(cfg), indent=1))
    elif mode == 'grid':
        cfgs = list(grid())
        with Pool(4, initializer=load_all) as pool:
            results = pool.map(run_cfg, cfgs, chunksize=8)
        json.dump(results, open(sys.argv[2], 'w'))
        print(f'{len(results)} configs written to {sys.argv[2]}')
