"""Live rotation monitor. Runs from GitHub Actions.

    python monitor.py check                 # scheduled check (1st / 15th)
    python monitor.py reminder              # Monday: nag while a switch issue is open
    python monitor.py test <kind>           # send a fake alert: routine|watch|switch|data_error
"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from pierg import alerts, rules, signals
from pierg import config as C
from pierg.data import fetch_fred, fetch_prices

STATE = Path("state/state.json")
LOG = Path("state/checks_log.csv")
MAX_STALE_DAYS = 5          # newest close must be at most this many calendar days old
MAX_DAILY_MOVE = 0.25       # a >25% one-day move in any input = suspicious data


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"mode": "Normal", "streak": 0, "last_eval": None, "open_issue": None}


def save_state(s):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2) + "\n")


def weights_text(mode):
    w = C.NORMAL if mode == "Normal" else C.ROTATION
    return "\n".join(f"  {k}: {int(round(v * 100))}%" for k, v in w.items())


def switch_steps(new_mode):
    old = "Rotation" if new_mode == "Normal" else "Normal"
    add = "Add 4GLD (Xetra-Gold) to the pie. " if new_mode == "Rotation" else "Remove 4GLD from the pie. "
    return (f"Pie targets now ({new_mode} mode):\n{weights_text(new_mode)}\n\n"
            f"Steps in the Trading 212 app (during Xetra hours, 10:00-18:30 Sofia time):\n"
            f"  1. Open the pie -> Edit pie.\n"
            f"  2. {add}Set the weights above (they must total 100%).\n"
            f"  3. Save, then tap Rebalance and confirm.\n"
            f"  4. Close the GitHub issue 'Switch pie to {new_mode}' so the Monday reminders stop.\n"
            f"(Previous mode was {old}.)")


def signal_lines(row):
    lines = []
    for k, label in C.SIGNAL_NAMES.items():
        lines.append(f"  {'TRUE ' if row[k] == 1 else 'false'}  {label}")
    lines.append(f"  RSP/SPY vs 200d {row['rsp_spy_vs_ma_pct']:+.1f}% | IWD/IWF {row['iwd_iwf_vs_ma_pct']:+.1f}% | "
                 f"SOXX/SPY {row['soxx_spy_vs_ma_pct']:+.1f}% | credit +{row['credit_widening']:.2f}pp | 10y {row['y10']:.2f}%")
    return "\n".join(lines)


def data_problems(px, sig, today):
    probs = []
    if not len(sig):
        return ["no signal rows at all"]
    ev = sig.index[-1]
    age = (pd.Timestamp(today) - ev).days
    if age > MAX_STALE_DAYS:
        probs.append(f"newest close is {ev.date()} ({age} days old)")
    if not bool(sig.loc[ev, "valid"]):
        missing = [k for k in ("s1", "s2", "s3", "s4", "s5") if pd.isna(sig.loc[ev, k])]
        probs.append(f"missing inputs on {ev.date()}: {', '.join(missing)}")
    cols = ["SPY", "RSP", "IWD", "IWF", "SOXX"]
    moves = px[cols].pct_change().iloc[-5:].abs().max()
    bad = moves[moves > MAX_DAILY_MOVE]
    if len(bad):
        probs.append("implausible one-day moves: " + ", ".join(f"{k} {v:.0%}" for k, v in bad.items()))
    return probs


def log_row(d):
    LOG.parent.mkdir(exist_ok=True)
    df = pd.DataFrame([d])
    df.to_csv(LOG, mode="a", header=not LOG.exists(), index=False)


def notify(kind, title, body):
    errs = alerts.send(kind, title, body)
    for e in errs:
        print(f"WARNING one channel failed: {e}")


def cmd_check():
    variant = C.VARIANTS[C.ACTIVE_VARIANT]
    confirm = variant["confirm"]
    state = load_state()
    today = datetime.now(timezone.utc).date()
    try:
        px = fetch_prices([t for t in C.PRICE_TICKERS if t not in ("EURUSD=X",)], start="2024-01-01")
        fred = fetch_fred(["DGS10", C.LIVE_CREDIT_SERIES])
        thr = C.HY_THRESHOLD if C.LIVE_CREDIT_SERIES == "BAMLH0A0HYM2" else C.BAA_FALLBACK_THRESHOLD
        sig = signals.build(px, fred, C.LIVE_CREDIT_SERIES, thr)
        sig = sig[sig.index < pd.Timestamp(today)]      # only closes before today
        probs = data_problems(px[px.index < pd.Timestamp(today)], sig, today)
    except Exception as e:  # noqa: BLE001
        probs, sig = [f"download/compute failed: {e!r}"], None

    if probs:
        body = ("This check does NOT count toward a switch. Mode stays " + state["mode"] +
                f", streak {state['streak']}/{confirm} unchanged.\n\nProblems:\n- " + "\n- ".join(probs) +
                "\n\nNext scheduled check will try again. If this repeats, tell Claude.")
        notify("DATA_ERROR", f"Data error - check skipped ({today})", body)
        log_row({"run_date": str(today), "eval_date": None, "n": None, "mode": state["mode"],
                 "streak": state["streak"], "action": "DATA_ERROR", "note": "; ".join(probs)})
        save_state(state)
        return

    ev = sig.index[-1]
    row = sig.loc[ev]
    if state.get("last_eval") == str(ev.date()):
        print(f"already evaluated {ev.date()}, nothing to do")
        return

    n = int(row["n"])
    mode, streak, action = rules.step(state["mode"], state["streak"], n, confirm)
    head = f"{n}/5 signals true on {ev.date()} close."
    if action == "ROUTINE":
        kind, title = "ROUTINE", f"{n}/5 - stay {mode}"
        body = f"{head} Mode: {mode}. Nothing to do.\n\n{signal_lines(row)}"
    elif action == "WATCH":
        need = (f">= {C.ENTER_MIN}" if mode == "Normal" else f"<= {C.EXIT_MAX}")
        target = "Rotation" if mode == "Normal" else "Normal"
        kind, title = "WATCH", f"WATCH {n}/5 - {streak}/{confirm} toward {target}"
        body = (f"{head} Condition for {target} ({need} signals) met {streak} of {confirm} checks in a row.\n"
                f"No action yet. A switch fires if it holds for {confirm - streak} more check(s).\n\n{signal_lines(row)}")
    else:
        kind, title = "SWITCH", f"SWITCH pie to {mode} mode"
        body = f"{head} The rule fired.\n\n{switch_steps(mode)}\n\nSignals:\n{signal_lines(row)}"
        try:
            state["open_issue"] = alerts.open_issue(f"Switch pie to {mode}", body)
        except Exception as e:  # noqa: BLE001
            print(f"WARNING could not open issue: {e!r}")
    notify(kind, title, body)

    state.update({"mode": mode, "streak": streak, "last_eval": str(ev.date()),
                  "last_n": n, "last_run": str(today)})
    save_state(state)
    log_row({"run_date": str(today), "eval_date": str(ev.date()), "n": n, "mode": mode,
             "streak": streak, "action": action, "note": ""})


def cmd_reminder():
    state = load_state()
    num = state.get("open_issue")
    if not num:
        print("no open switch issue")
        return
    if alerts.issue_is_open(num):
        notify("REMINDER", f"Reminder: pie switch to {state['mode']} not confirmed",
               f"GitHub issue #{num} is still open.\n\n{switch_steps(state['mode'])}")
    else:
        state["open_issue"] = None
        save_state(state)
        print(f"issue #{num} closed, reminders stopped")


def cmd_test(kind):
    kind = kind.upper()
    fake = {"s1": 1, "s2": 1, "s3": 1, "s4": 0, "s5": 0, "rsp_spy_vs_ma_pct": 1.2, "iwd_iwf_vs_ma_pct": 0.8,
            "soxx_spy_vs_ma_pct": -3.4, "credit_widening": 0.35, "y10": 5.10}
    tag = "[TEST - ignore] "
    if kind == "ROUTINE":
        notify("ROUTINE", tag + "2/5 - stay Normal", "Test of the routine message.\n\n" + signal_lines(fake))
    elif kind == "WATCH":
        notify("WATCH", tag + "WATCH 3/5 - 1/2 toward Rotation", "Test of the watch message.\n\n" + signal_lines(fake))
    elif kind == "SWITCH":
        notify("SWITCH", tag + "SWITCH pie to Rotation mode",
               "Test of the switch message. DO NOT change your pie.\n\n" + switch_steps("Rotation"))
    elif kind == "DATA_ERROR":
        notify("DATA_ERROR", tag + "Data error - check skipped", "Test of the data-error message.")
    else:
        raise SystemExit(f"unknown test kind {kind}")
    print(f"sent test {kind}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    {"check": lambda: cmd_check(), "reminder": lambda: cmd_reminder(),
     "test": lambda: cmd_test(sys.argv[2] if len(sys.argv) > 2 else "")}[sys.argv[1]]()
