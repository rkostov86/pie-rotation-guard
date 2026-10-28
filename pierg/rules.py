"""Check schedule and the Normal/Rotation state machine."""
from dataclasses import dataclass, field

import pandas as pd

from . import config as C


def check_points(index, schedule, start=None):
    """Each check = (alert_date, eval_date, exec_date).

    alert_date: the 1st (and 15th) of the month, when the job runs.
    eval_date:  last close BEFORE the alert date (data the job can see).
    exec_date:  first trading day on/after the alert date (when Rumba rebalances), or None if future.
    """
    start = pd.Timestamp(start) if start is not None else index[0]
    months = pd.date_range(start.to_period("M").to_timestamp(), index[-1] + pd.offsets.MonthBegin(1), freq="MS")
    anchors = []
    for m in months:
        anchors.append(m)
        if schedule == "semimonthly":
            anchors.append(m + pd.Timedelta(days=14))
    out, seen = [], set()
    for a in anchors:
        pos = index.searchsorted(a) - 1
        if pos < 0:
            continue
        ev = index[pos]
        if ev < start or ev in seen:
            continue
        seen.add(ev)
        epos = index.searchsorted(a)
        ex = index[epos] if epos < len(index) else None
        out.append((a, ev, ex))
    return out


@dataclass
class RunResult:
    checks: pd.DataFrame
    events: list = field(default_factory=list)   # (exec_date, new_mode, alert_date)
    mode_now: str = "Normal"
    streak_now: int = 0


def step(mode, streak, n, confirm):
    """One check of the state machine. Shared by the backtest and the live monitor.

    Returns (new_mode, new_streak, action) where action is ROUTINE, WATCH or SWITCH_TO_<MODE>.
    """
    cond = n >= C.ENTER_MIN if mode == "Normal" else n <= C.EXIT_MAX
    streak = streak + 1 if cond else 0
    if cond and streak >= confirm:
        mode = "Rotation" if mode == "Normal" else "Normal"
        return mode, 0, f"SWITCH_TO_{mode.upper()}"
    return mode, streak, ("WATCH" if cond else "ROUTINE")


def run(sig, schedule, confirm, start_mode="Normal"):
    mode, streak = start_mode, 0
    rows, events = [], []
    valid_start = sig.index[sig["valid"]][0]
    for alert, ev, ex in check_points(sig.index, schedule, start=valid_start):
        r = sig.loc[ev]
        if not bool(r["valid"]):
            rows.append(dict(alert=alert, eval=ev, exec=ex, n=None, mode=mode, streak=streak, action="DATA_ERROR"))
            continue  # bad data never counts, and does not reset the streak
        n = int(r["n"])
        mode, streak, action = step(mode, streak, n, confirm)
        if action.startswith("SWITCH") and ex is not None:
            events.append((ex, mode, alert))
        rows.append(dict(alert=alert, eval=ev, exec=ex, n=n, mode=mode, streak=streak, action=action))
    return RunResult(pd.DataFrame(rows), events, mode, streak)


def episodes(events, end):
    """Rotation episodes as (entry_exec, exit_exec_or_None)."""
    eps, entry = [], None
    for d, m, _ in events:
        if m == "Rotation":
            entry = d
        elif entry is not None:
            eps.append((entry, d))
            entry = None
    if entry is not None:
        eps.append((entry, None))
    return eps
