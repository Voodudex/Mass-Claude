---
name: options-signals
description: One-minute-chart options entry signals from three triggers — candle close across VWAP, candle close across the 50 EMA, or a close outside the first-15-minute opening range. Close above = buy a call, close below = buy a put. Use when asked to scan price data for these signals, explain or backtest this strategy, or build/review a trading agent based on it. Learned from an Instagram reel by Nicholas Fischer (@nickafischer).
license: MIT
allowed-tools: Bash, Read
metadata:
  version: "0.1.0"
  source: "https://www.instagram.com/reel/DeNQ-wOyoZt/ (summarized by the user; video not viewed)"
---

# Options entry signals: VWAP / 50 EMA / opening-range breakout

## Where this came from

An Instagram reel by Nicholas Fischer (@nickafischer) showing an agent that day-trades options for him from a dashboard. The user described it; the video itself was not viewed. Everything under **The strategy as described** comes from that description. Everything under **Not specified** is a gap the source did not cover — never present those defaults as his method.

## The strategy as described

- **Instrument:** options (calls and puts).
- **Chart:** 1-minute candles.
- **Entry triggers** — any one fires a trade, judged on the **candle close**, not intrabar:
  1. **VWAP cross:** a 1-minute candle closes across VWAP.
  2. **50 EMA cross:** a 1-minute candle closes across the 50-period EMA.
  3. **Opening-range breakout:** price closes outside the range (high/low) of the first 15 minutes of the session.
- **Direction:** close **above** the level → **buy a call**. Close **below** → **buy a put**.

## Precise rules used by the script

These make the description testable. They are interpretations; confirm or change them with the user.

| Rule | Interpretation |
|---|---|
| Session | US regular hours, 09:30–16:00 Eastern. Pre/after-market bars ignored. |
| VWAP | Session VWAP from 09:30, typical price (H+L+C)/3 × volume, resets daily. |
| 50 EMA | EMA of 1-minute closes, carried across days, needs 50 bars of warm-up. |
| "Closes across" | Previous close at/below the level and this close above it (call), or the reverse (put). |
| Opening range | High and low of 09:30–09:44 bars. Breakout = first close above the high (call) or below the low (put) from 09:45 on; each side fires at most once per day. |
| Conflicts | Triggers on the same bar pointing opposite ways are flagged `CONFLICT`. |

## Not specified by the source — ask before acting

The reel summary only covers **entries**. A working agent also needs:

- **Exits:** profit target, stop loss, time stop, or exit on the opposite signal.
- **Contract choice:** underlying (SPY/QQQ/single stocks?), expiration (0DTE?), strike (ATM, 1 strike OTM, by delta).
- **Size and limits:** contracts per trade, max trades/day, max daily loss, one position at a time or several.
- **Filters:** no-trade windows (e.g. right after the open), chop filter (VWAP and EMA crosses fire constantly in sideways markets), whether triggers need to agree.
- **Platform:** the "dashboard" and broker the agent trades through.

When building or reviewing an agent from this skill, list whichever of these are still open.

## Using the script

```bash
python3 "${SKILL_DIR}/scripts/signals.py" bars.csv            # every signal in the file
python3 "${SKILL_DIR}/scripts/signals.py" bars.csv --latest   # only the newest bar (live check)
python3 "${SKILL_DIR}/scripts/signals.py" bars.csv --json
```

CSV header: `timestamp,open,high,low,close,volume`, timestamps in US/Eastern exchange time. Standard library only.

## Backtest results (Nov 2024 – Nov 2026, SPY & QQQ, 1-minute bars from Polygon)

Model: 0DTE nearest-strike options priced with Black-Scholes (IV = 1.2 × trailing 10-day realized vol), entry at the next bar's open, $0.02/share per side spread + $0.65/contract commission. Rules were chosen on Nov 2024 – Dec 2025 and tested once on Jan – Nov 2026.

- **Literal rules (every signal, exit on opposite signal):** SPY lost about $139k on 1 contract per trade over 2 years (~39 trades/day, 13% win rate, 0 profitable months). VWAP and EMA crosses fire ~47 times a day combined.
- **1,792 rule variants** (trigger subsets, trend filter, time windows, 25/50% stops, 50/100% targets, 15/45-min time stops, opposite-signal exit, 2 or 10 trades/day): only 2 were profitable on both tickers in the training period, both near break-even (profit factor ≤ 1.09). The best one — ORB only, 50% stop, 100% target, 45-min time stop — was flat on SPY and lost $2.9k on QQQ in the test period.
- **No directional edge before costs:** average move after each trigger, in the signal's direction, is within ±0.3 basis points at 5–60 minutes for VWAP and EMA crosses on both tickers. ORB showed +2 to +5 bp at 60 minutes in 2025 that disappeared or reversed in 2026.
- **The model is likely optimistic:** real 0DTE implied vol usually trades above realized, so real premiums would cost more than modeled.

Conclusion: with these three triggers, no tested exit or filter produced consistent profit. Further parameter searching on the same triggers would mostly fit noise. New ideas should start from a stated reason for an edge and be tested the same way (choose on one period, judge on an unseen later one, costs included).

## Safety rules for any agent built from this

- The script **only reports signals**. Never place, modify or cancel a real order without the user's explicit go-ahead for that specific action, and default to paper trading.
- Before suggesting real money, backtest on historical 1-minute data including option premiums, spreads and commissions — signal counts alone say nothing about profitability.
- Short-dated options can lose their full premium within minutes. Point out missing stop/size/daily-loss rules rather than inventing them silently.
- A reel showing wins is not evidence the strategy is profitable. Say so if asked whether it works.
