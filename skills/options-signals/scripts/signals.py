#!/usr/bin/env python3
"""Scan 1-minute bars for the three entry triggers and print call/put signals.

Triggers (evaluated on each CLOSED 1-minute candle, regular session only):
  vwap  - close crosses session VWAP (resets each day at the open)
  ema50 - close crosses the 50-period EMA of 1-minute closes
  orb   - close breaks out of the first-15-minute opening range (once per side per day)
Close above -> CALL, close below -> PUT.

Input CSV columns (header required): timestamp,open,high,low,close,volume
Timestamps are exchange-local time (US/Eastern), e.g. 2026-11-05 09:31:00 or ISO 8601.
Standard library only. This produces signals; it never places orders.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, time

OPEN, OR_END, CLOSE = time(9, 30), time(9, 45), time(16, 0)


def load(path):
    bars = []
    with open(path, newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            row = {k.strip().lower(): v for k, v in row.items()}
            ts = datetime.fromisoformat(row['timestamp'].strip().replace('Z', '+00:00'))
            bars.append({'ts': ts.replace(tzinfo=None), **{k: float(row[k]) for k in ('open', 'high', 'low', 'close', 'volume')}})
    bars.sort(key=lambda b: b['ts'])
    return [b for b in bars if OPEN <= b['ts'].time() < CLOSE]


def crossed(prev_close, close, prev_level, level):
    """+1 for a close crossing up through the level, -1 for down, 0 otherwise."""
    if prev_close <= prev_level and close > level:
        return 1
    if prev_close >= prev_level and close < level:
        return -1
    return 0


def scan(bars, ema_period=50):
    k = 2 / (ema_period + 1)
    signals, ema, count = [], None, 0
    day = prev = None
    for bar in bars:
        if bar['ts'].date() != day:  # New session: reset VWAP and the opening range.
            day, pv, vol = bar['ts'].date(), 0.0, 0.0
            or_high, or_low, or_fired, prev = float('-inf'), float('inf'), set(), None
        typical = (bar['high'] + bar['low'] + bar['close']) / 3
        pv += typical * bar['volume']
        vol += bar['volume']
        vwap = pv / vol if vol else typical
        ema = bar['close'] if ema is None else bar['close'] * k + ema * (1 - k)
        count += 1
        ema_ready = count >= ema_period  # EMA carries across days; needs a warm-up.
        t = bar['ts'].time()
        hits = []
        if prev is not None:
            side = crossed(prev['close'], bar['close'], prev['vwap'], vwap)
            if side:
                hits.append(('vwap', side, vwap))
            if ema_ready and prev['ema_ready']:
                side = crossed(prev['close'], bar['close'], prev['ema'], ema)
                if side:
                    hits.append(('ema50', side, ema))
        if t < OR_END:
            or_high, or_low = max(or_high, bar['high']), min(or_low, bar['low'])
        elif or_high > float('-inf'):
            if bar['close'] > or_high and 'up' not in or_fired:
                or_fired.add('up')
                hits.append(('orb', 1, or_high))
            elif bar['close'] < or_low and 'down' not in or_fired:
                or_fired.add('down')
                hits.append(('orb', -1, or_low))
        sides = {side for _, side, _ in hits}
        for trigger, side, level in hits:
            signals.append({'time': bar['ts'].isoformat(sep=' '), 'trigger': trigger,
                            'signal': 'CALL' if side > 0 else 'PUT', 'close': bar['close'],
                            'level': round(level, 4), 'conflict': len(sides) > 1})
        prev = {'close': bar['close'], 'vwap': vwap, 'ema': ema, 'ema_ready': ema_ready}
    return signals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv', help='1-minute OHLCV CSV')
    ap.add_argument('--latest', action='store_true', help='only report signals on the most recent bar (live check)')
    ap.add_argument('--json', action='store_true', help='print JSON instead of a table')
    ap.add_argument('--ema', type=int, default=50, help='EMA period (default 50)')
    args = ap.parse_args()
    bars = load(args.csv)
    if not bars:
        raise SystemExit('No regular-session bars (09:30-16:00) found in the file.')
    signals = scan(bars, args.ema)
    if args.latest:
        last = bars[-1]['ts'].isoformat(sep=' ')
        signals = [s for s in signals if s['time'] == last]
    if args.json:
        print(json.dumps(signals, indent=2))
        return
    if not signals:
        print('No signals.')
        return
    print(f"{'time':19}  {'trigger':7}  {'signal':6}  {'close':>10}  {'level':>10}")
    for s in signals:
        flag = '  CONFLICT' if s['conflict'] else ''
        print(f"{s['time']:19}  {s['trigger']:7}  {s['signal']:6}  {s['close']:>10.2f}  {s['level']:>10.2f}{flag}")


if __name__ == '__main__':
    sys.exit(main())
