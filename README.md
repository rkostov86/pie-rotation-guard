# pie-rotation-guard — ARCHIVED (28 Oct 2026)

**Decision: no automatic switching.** Keep the Normal pie and keep depositing. Nothing in this repo runs anymore.

## What was tested
A rule to move the Trading 212 pie from Normal to a defensive Rotation mode when the market rotates away from AI/tech:
5 signals (equal weight vs cap weight, value vs growth, chips vs market, credit spreads, 10-year yield),
switch when ≥3 are true for N consecutive checks, switch back when ≤1 are true.

Pass criteria were fixed **before** any results: ≤6 switches 2004–2026, in Rotation during the 2008 and 2022 declines,
≤2 false alarms, one tuning round allowed.

## Result
| Version | Switches | False alarms | 10k EUR became |
|---|---|---|---|
| Never switch (Normal pie) | 0 | — | 89,200 |
| A monthly / 2 checks | 16 | 2 | 86,100 |
| B 1st&15th / 2 checks | 20 | 3 | 84,900 |
| C 1st&15th / 4 checks | 14 | 1 | 85,600 |
| A2 (tuned) monthly / 3 | 12 | 0 | 84,300 |
| C2 (tuned) 1st&15th / 6 | 12 | 0 | 83,600 |

No version passed. All switched too often and entered Rotation after most of the 2008 / 2022 damage,
saving only 1–3 points of drawdown while costing 0.2–0.35%/year. Full report: `results/backtest_report.md`.

## Normal pie (kept)
SXR8 35% · XNAQ 20% · IXUA 20% · SPYD 15% · XDEW 10%

## Contents
- `backtest.py`, `pierg/` — data download, signals, rule engine, EUR portfolio simulation
- `monitor.py`, `pierg/alerts.py` — live monitor (built, never deployed)
- `SETUP.md` — secrets guide (not needed while archived)
- `results/` — backtest outputs
