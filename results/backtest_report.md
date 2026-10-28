# Backtest report — pie-rotation-guard

Data through **2026-10-27**. Signals valid from **2004-02-13**; portfolio simulated in EUR from **2005-11-15** (first date all stand-in funds exist).

Credit signal used: **BAA10Y** (threshold 0.5 pp; history from 1999-01-04).

10-year yield >= 5.9% was true on **0** of 5712 test days.


## Verdict

**No variant passed all four criteria.** One round of tuning is allowed (see plan).


## Pass criteria

| | Variant A | Variant B | Variant C |
|---|---|---|---|
| Rule | Monthly, 2 checks (~2 months) | 1st & 15th, 2 checks (~4 weeks) | 1st & 15th, 4 checks (~2 months) |
| Switches (max 6) | 16 ❌ | 20 ❌ | 14 ❌ |
| In Rotation during 2008 decline | ✅ entry 2008-11-03 | ✅ entry 2008-10-01 | ✅ entry 2008-11-03 |
| In Rotation during 2022 decline | ✅ entry 2022-04-01 | ✅ entry 2022-03-01 | ✅ entry 2022-04-01 |
| False alarms (max 2) | 2 ✅ | 3 ❌ | 1 ✅ |
| **Passed all** | no | no | no |

## Performance in EUR (10,000 EUR start, stand-in funds)

| Strategy | Final value | CAGR | Max drawdown | 2008 decline | 2020 crash | 2022 decline | Time in Rotation | Switch costs |
|---|---|---|---|---|---|---|---|---|
| Always Normal | 89,228 | 11.01% | -50.8% | -50.0% | -32.6% | -16.6% | — | — |
| Variant A | 86,122 | 10.83% | -48.4% | -47.3% | -32.6% | -14.4% | 20% | 115 EUR |
| Variant B | 84,909 | 10.75% | -48.5% | -47.6% | -32.6% | -15.1% | 25% | 132 EUR |
| Variant C | 85,601 | 10.79% | -48.4% | -47.3% | -32.6% | -14.4% | 21% | 96 EUR |

## Variant A — Rotation episodes

| Entered | Exited | Days |
|---|---|---|
| 2004-05-03 | 2005-12-01 | 577 |
| 2006-07-03 | 2007-09-04 | 428 |
| 2008-11-03 | 2009-04-01 | 149 |
| 2010-07-01 | 2011-01-03 | 186 |
| 2013-01-02 | 2013-10-01 | 272 |
| 2019-02-01 | 2019-04-01 | 59 |
| 2022-04-01 | 2023-05-01 | 395 |
| 2025-05-01 | 2025-07-01 | 61 |

Now: **Normal** (last check on 2026-10-27 close: 1/5 signals true, streak 0).


## Variant B — Rotation episodes

| Entered | Exited | Days |
|---|---|---|
| 2004-04-15 | 2005-11-01 | 565 |
| 2006-06-01 | 2007-08-01 | 426 |
| 2008-10-01 | 2009-03-16 | 166 |
| 2010-06-01 | 2010-12-15 | 197 |
| 2012-01-17 | 2012-02-15 | 29 |
| 2012-12-03 | 2013-09-16 | 287 |
| 2016-05-16 | 2017-03-01 | 289 |
| 2019-01-15 | 2019-03-01 | 45 |
| 2022-03-01 | 2023-04-03 | 398 |
| 2025-04-01 | 2025-06-02 | 62 |

Now: **Normal** (last check on 2026-10-27 close: 1/5 signals true, streak 0).


## Variant C — Rotation episodes

| Entered | Exited | Days |
|---|---|---|
| 2004-05-17 | 2005-12-01 | 563 |
| 2006-07-03 | 2007-09-04 | 428 |
| 2008-11-03 | 2009-06-15 | 224 |
| 2010-07-01 | 2011-01-18 | 201 |
| 2013-01-02 | 2013-10-15 | 286 |
| 2022-04-01 | 2023-05-01 | 395 |
| 2025-05-01 | 2025-07-01 | 61 |

Now: **Normal** (last check on 2026-10-27 close: 1/5 signals true, streak 0).


## Signals at latest close (2026-10-27)

- false — Equal weight beating cap weight (RSP/SPY above 200d)
- TRUE  — Value beating growth (IWD/IWF above 200d)
- false — Chips lagging market (SOXX/SPY below 200d)
- false — Credit stress (spread >= threshold above 6-month low)
- false — 10-year yield >= 5.9%

RSP/SPY vs 200d: -0.73% · IWD/IWF vs 200d: +6.73% · SOXX/SPY vs 200d: +2.40% · credit widening: 0.06 pp · 10y: 5.00%


## Assumptions and limits

- US-listed stand-ins: SXR8→SPY, XNAQ→QQQ, IXUA→EFA (excludes Canada), SPYD→SDY, XDEW→RSP, 4GLD→GLD; converted to EUR daily.
- Switch trades executed at the close of the first trading day on/after the alert date; 0.1% cost on every euro traded.
- Monthly drift back to target assumed free (stands in for deposits); same for every strategy, so comparisons are fair.
- No taxes (ETF gains confirmed exempt), no dividend tax drag on SPYD, no deposits modelled.
- A backtest shows how the rule behaved on the past; it does not prove it will work in the next rotation.
