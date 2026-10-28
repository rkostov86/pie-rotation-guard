"""Backtest variants A/B/C against the pre-approved pass criteria.

Usage:
    python backtest.py              # real data (GitHub Actions)
    python backtest.py --synthetic  # offline smoke test with fake data
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from pierg import config as C
from pierg import portfolio, rules, signals
from pierg.data import fetch_fred, fetch_prices

OUT = Path("results")


def synthetic():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2001-01-02", "2026-10-27")
    n = len(idx)
    px = {}
    for t in C.PRICE_TICKERS:
        drift = 0.0 if t == "EURUSD=X" else 0.0003
        vol = 0.005 if t == "EURUSD=X" else 0.012
        start_at = {"RSP": "2003-05-01", "SDY": "2005-11-08", "GLD": "2004-11-18"}.get(t)
        s = pd.Series(100 * np.exp(np.cumsum(rng.normal(drift, vol, n))), index=idx)
        if t == "EURUSD=X":
            s = s / 100 * 1.2
        if start_at:
            s[s.index < start_at] = np.nan
        px[t] = s
    px = pd.DataFrame(px)
    fidx = pd.date_range("1990-01-01", "2026-10-27")
    m = len(fidx)
    fred = {
        "DGS10": pd.Series(4 + np.cumsum(rng.normal(0, 0.02, m)).clip(-3, 3), index=fidx),
        "BAMLH0A0HYM2": pd.Series(4 + np.abs(np.cumsum(rng.normal(0, 0.05, m))), index=fidx),
        "BAA10Y": pd.Series(2 + np.abs(np.cumsum(rng.normal(0, 0.02, m))), index=fidx),
    }
    return px, fred


def evaluate(name, spec, sig, pe, sim_start):
    res = rules.run(sig, spec["schedule"], spec["confirm"])
    events = res.events
    switches = len(events)
    eps = rules.episodes(events, sig.index[-1])
    false_alarms = [(a, b) for a, b in eps if b is not None and (b - a).days <= C.FALSE_ALARM_DAYS]

    caught = {}
    for label, (a, b) in C.MUST_CATCH.items():
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        hit = [(x, y) for x, y in eps if x <= b and (y is None or y >= a)]
        caught[label] = {"caught": bool(hit), "entry": str(hit[0][0].date()) if hit else None}

    initial = "Normal"
    for d, m, _ in events:
        if d < sim_start:
            initial = m
    v, modes, costs = portfolio.simulate(pe, events, sim_start, initial_mode=initial)

    passes = {
        "switches_ok": switches <= C.MAX_SWITCHES,
        "caught_2008": caught["2008"]["caught"],
        "caught_2022": caught["2022"]["caught"],
        "false_alarms_ok": len(false_alarms) <= C.MAX_FALSE_ALARMS,
    }
    last = res.checks.iloc[-1]
    return {
        "variant": name,
        "label": spec["label"],
        "switches": switches,
        "switch_log": [{"exec": str(d.date()), "to": m, "alert": str(a.date())} for d, m, a in events],
        "episodes": [{"entry": str(a.date()), "exit": str(b.date()) if b is not None else "still in Rotation",
                      "days": (b - a).days if b is not None else None} for a, b in eps],
        "false_alarms": len(false_alarms),
        "caught": caught,
        "pass": passes,
        "passed_all": all(passes.values()),
        "time_in_rotation_pct": float((modes == "Rotation").mean() * 100),
        "switch_costs_eur": float(costs),
        "metrics": portfolio.metrics(v),
        "dd_2008_pct": portfolio.window_drawdown(v, *C.MUST_CATCH["2008"]),
        "dd_2022_pct": portfolio.window_drawdown(v, *C.MUST_CATCH["2022"]),
        "dd_2020_pct": portfolio.window_drawdown(v, "2020-02-19", "2020-03-23"),
        "now": {"mode": res.mode_now, "streak": int(res.streak_now),
                "last_check_eval": str(pd.Timestamp(last["eval"]).date()),
                "last_n": None if last["n"] is None else int(last["n"])},
        "_series": v,
    }


def pick_winner(results):
    passing = [r for r in results if r["passed_all"]]
    if not passing:
        return None
    order = {"A": 0, "B": 1, "C": 2}
    return sorted(passing, key=lambda r: (r["false_alarms"], r["switches"], order[r["variant"]]))[0]["variant"]


def yearly(series):
    s = series.groupby(series.index.year).last()
    return {int(k): round(float(x), 2) for k, x in s.items()}


def write_report(meta, base, results, winner, sig):
    L = []
    L.append("# Backtest report — pie-rotation-guard\n")
    L.append(f"Data through **{meta['data_end']}**. Signals valid from **{meta['signal_start']}**; "
             f"portfolio simulated in EUR from **{meta['sim_start']}** (first date all stand-in funds exist).\n")
    L.append(f"Credit signal used: **{meta['credit_series']}** (threshold {meta['credit_threshold']} pp; "
             f"history from {meta['credit_history_start']}).\n")
    L.append(f"10-year yield >= {C.YIELD_THRESHOLD}% was true on **{meta['s5_true_days']}** of "
             f"{meta['signal_days']} test days.\n")
    L.append("\n## Verdict\n")
    if winner:
        L.append(f"**Winner: Variant {winner}** — passes all four pre-approved criteria with the fewest false alarms.\n")
    else:
        L.append("**No variant passed all four criteria.** One round of tuning is allowed (see plan).\n")
    L.append("\n## Pass criteria\n")
    L.append("| | " + " | ".join(f"Variant {r['variant']}" for r in results) + " |")
    L.append("|---|" + "---|" * len(results))
    L.append("| Rule | " + " | ".join(r["label"] for r in results) + " |")
    L.append(f"| Switches (max {C.MAX_SWITCHES}) | " + " | ".join(
        f"{r['switches']} {'✅' if r['pass']['switches_ok'] else '❌'}" for r in results) + " |")
    for lab in ("2008", "2022"):
        L.append(f"| In Rotation during {lab} decline | " + " | ".join(
            (f"✅ entry {r['caught'][lab]['entry']}" if r['caught'][lab]['caught'] else "❌") for r in results) + " |")
    L.append(f"| False alarms (max {C.MAX_FALSE_ALARMS}) | " + " | ".join(
        f"{r['false_alarms']} {'✅' if r['pass']['false_alarms_ok'] else '❌'}" for r in results) + " |")
    L.append("| **Passed all** | " + " | ".join("**yes**" if r["passed_all"] else "no" for r in results) + " |")

    L.append("\n## Performance in EUR (10,000 EUR start, stand-in funds)\n")
    L.append("| Strategy | Final value | CAGR | Max drawdown | 2008 decline | 2020 crash | 2022 decline | Time in Rotation | Switch costs |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    rows = [("Always Normal", base, None)] + [(f"Variant {r['variant']}", r, r) for r in results]
    for name, m, r in rows:
        mm = m["metrics"]
        L.append(f"| {name} | {mm['final_value']:,.0f} | {mm['cagr_pct']:.2f}% | {mm['max_drawdown_pct']:.1f}% | "
                 f"{m['dd_2008_pct']:.1f}% | {m['dd_2020_pct']:.1f}% | {m['dd_2022_pct']:.1f}% | "
                 f"{'—' if r is None else f'{r['time_in_rotation_pct']:.0f}%'} | "
                 f"{'—' if r is None else f'{r['switch_costs_eur']:,.0f} EUR'} |")

    for r in results:
        L.append(f"\n## Variant {r['variant']} — Rotation episodes\n")
        if not r["episodes"]:
            L.append("None.\n")
            continue
        L.append("| Entered | Exited | Days |")
        L.append("|---|---|---|")
        for e in r["episodes"]:
            L.append(f"| {e['entry']} | {e['exit']} | {e['days'] if e['days'] is not None else '—'} |")
        L.append(f"\nNow: **{r['now']['mode']}** (last check on {r['now']['last_check_eval']} close: "
                 f"{r['now']['last_n']}/5 signals true, streak {r['now']['streak']}).\n")

    last = sig[sig["valid"]].iloc[-1]
    L.append(f"\n## Signals at latest close ({sig[sig['valid']].index[-1].date()})\n")
    for k, label in C.SIGNAL_NAMES.items():
        L.append(f"- {'TRUE ' if last[k] == 1 else 'false'} — {label}")
    L.append(f"\nRSP/SPY vs 200d: {last['rsp_spy_vs_ma_pct']:+.2f}% · IWD/IWF vs 200d: {last['iwd_iwf_vs_ma_pct']:+.2f}% · "
             f"SOXX/SPY vs 200d: {last['soxx_spy_vs_ma_pct']:+.2f}% · credit widening: {last['credit_widening']:.2f} pp · "
             f"10y: {last['y10']:.2f}%\n")

    L.append("\n## Assumptions and limits\n")
    L.append("- US-listed stand-ins: SXR8→SPY, XNAQ→QQQ, IXUA→EFA (excludes Canada), SPYD→SDY, XDEW→RSP, 4GLD→GLD; converted to EUR daily.")
    L.append("- Switch trades executed at the close of the first trading day on/after the alert date; 0.1% cost on every euro traded.")
    L.append("- Monthly drift back to target assumed free (stands in for deposits); same for every strategy, so comparisons are fair.")
    L.append("- No taxes (ETF gains confirmed exempt), no dividend tax drag on SPYD, no deposits modelled.")
    L.append("- A backtest shows how the rule behaved on the past; it does not prove it will work in the next rotation.")
    (OUT / "backtest_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    if "--synthetic" in sys.argv:
        px, fred = synthetic()
    else:
        px = fetch_prices(C.PRICE_TICKERS, start="2000-01-01")
        fred = fetch_fred(C.FRED_SERIES)

    rsp_start = px["RSP"].first_valid_index()
    needed_from = rsp_start + pd.Timedelta(days=300)
    credit_sid, credit_thr = signals.pick_credit_series(fred, needed_from)
    sig = signals.build(px, fred, credit_sid, credit_thr)
    sig_valid = sig[sig["valid"]]

    pe = portfolio.eur_prices(px)
    sim_start = pe.dropna().index[0]
    base_v, _, _ = portfolio.simulate(pe, [], sim_start)
    base = {"metrics": portfolio.metrics(base_v),
            "dd_2008_pct": portfolio.window_drawdown(base_v, *C.MUST_CATCH["2008"]),
            "dd_2022_pct": portfolio.window_drawdown(base_v, *C.MUST_CATCH["2022"]),
            "dd_2020_pct": portfolio.window_drawdown(base_v, "2020-02-19", "2020-03-23")}

    results = [evaluate(k, spec, sig, pe, sim_start) for k, spec in C.VARIANTS.items()]
    winner = pick_winner(results)

    meta = {
        "data_end": str(px.index[-1].date()),
        "signal_start": str(sig_valid.index[0].date()),
        "sim_start": str(sim_start.date()),
        "credit_series": credit_sid,
        "credit_threshold": credit_thr,
        "credit_history_start": str(fred[credit_sid].index[0].date()),
        "s5_true_days": int(sig_valid["s5"].sum()),
        "signal_days": int(len(sig_valid)),
        "synthetic": "--synthetic" in sys.argv,
    }
    write_report(meta, base, results, winner, sig)

    yearly_values = {"Always Normal": yearly(base_v)}
    for r in results:
        yearly_values[f"Variant {r['variant']}"] = yearly(r.pop("_series"))
    summary = {"meta": meta, "winner": winner, "always_normal": base, "variants": results,
               "yearly_values": yearly_values}
    (OUT / "backtest_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    sig.tail(400).round(4).to_csv(OUT / "signals_recent.csv")
    print(json.dumps({"winner": winner, **meta}, indent=2))


if __name__ == "__main__":
    main()
