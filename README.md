# Mass-Claude

Skills for Claude Code, mostly learned from videos.

## Skills

| Skill | What it does | Source |
|---|---|---|
| [`watch`](skills/watch/SKILL.md) | Watches a video (URL or file) through Gemini, or extracts frames and captions locally, so Claude can answer questions about it. | [bradautomates/claude-video](https://github.com/bradautomates/claude-video) v0.3.2, MIT licence (kept in `skills/watch/LICENSE`) |
| [`options-signals`](skills/options-signals/SKILL.md) | One-minute options entry signals: candle close across VWAP, the 50 EMA, or the first 15-minute range. Includes a signal scanner and a 2-year SPY/QQQ backtest showing the rules did not make money. | Instagram reel by @nickafischer, as described by the user |
| [`smc-bootcamp`](skills/smc-bootcamp/SKILL.md) | A 55-day "smart money" day-trading course condensed: daily bias, liquidity sweeps, break of structure, fair value gaps, order blocks, equilibrium, risk, sessions, news, trading plan and journal. Per-lesson notes are in `source-notes/`. | YouTube playlist `PLKE_22Jx497twaT62Qv9DAiagynP4dAYV` |
| [`humanize`](skills/humanize/SKILL.md) | Rewrites text in the user's own voice: first person, plain words, some run-on sentences, and common AI-writing patterns removed. Run it with `/humanize <text>`. | Written with the user in a Claude Code session |

## Use in a Claude Code session

Start a session with this repository selected, then run:

```bash
bash install.sh
```

This copies every skill into `~/.claude/skills/` so Claude can use them in that session.

The `watch` skill also needs a Gemini API key (free at https://aistudio.google.com/apikey). Add `GEMINI_API_KEY` as an environment variable in the cloud environment's settings. Never commit a key to this repository.

## Notes

- Trading skills are for analysis and paper trading. They never place real orders. Nothing here is financial advice, and none of the strategies has a proven track record.
- Notes made from videos were written by Gemini watching each one and were not checked against captions, so exact wording may be off.
