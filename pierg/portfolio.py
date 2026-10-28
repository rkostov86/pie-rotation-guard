"""Simulate the pie in EUR using the US stand-in funds."""
import numpy as np
import pandas as pd

from . import config as C


def eur_prices(px):
    assets = sorted(set(C.PROXY.values()))
    # EURUSD=X is USD per 1 EUR -> EUR price = USD price / rate
    return px[assets].div(px["EURUSD=X"], axis=0)


def _target(mode, cols):
    w = C.NORMAL if mode == "Normal" else C.ROTATION
    v = pd.Series(0.0, index=cols)
    for fund, wt in w.items():
        v[C.PROXY[fund]] += wt
    return v.values


def simulate(pe, events, start, initial_mode="Normal", cost=C.SWITCH_COST, start_value=10_000.0):
    pe = pe.loc[start:].dropna()
    cols = list(pe.columns)
    dates = pe.index
    prices = pe.values
    month_end = set(pd.Series(dates, index=dates).groupby(dates.to_period("M")).max().values)
    ev = {pd.Timestamp(d): m for d, m, _ in events if d is not None and d >= dates[0]}

    mode = initial_mode
    w = _target(mode, cols)
    hold = start_value * w / prices[0]
    values, modes, costs = np.empty(len(dates)), [], 0.0
    for i, d in enumerate(dates):
        val = float(hold @ prices[i])
        if d in ev and ev[d] != mode:
            mode = ev[d]
            cur = hold * prices[i] / val
            tgt = _target(mode, cols)
            c = cost * np.abs(tgt - cur).sum() * val
            costs += c
            val -= c
            hold = val * tgt / prices[i]
        elif d in month_end:  # monthly drift correction (deposits/pie rebalancing), assumed free
            hold = val * _target(mode, cols) / prices[i]
        values[i] = val
        modes.append(mode)
    return pd.Series(values, index=dates), pd.Series(modes, index=dates), costs


def metrics(v):
    yrs = (v.index[-1] - v.index[0]).days / 365.25
    dd = v / v.cummax() - 1
    return {
        "final_value": float(v.iloc[-1]),
        "cagr_pct": float(((v.iloc[-1] / v.iloc[0]) ** (1 / yrs) - 1) * 100),
        "max_drawdown_pct": float(dd.min() * 100),
        "max_drawdown_date": str(dd.idxmin().date()),
    }


def window_drawdown(v, a, b):
    w = v.loc[a:b]
    if w.empty:
        return None
    return float((w / w.cummax() - 1).min() * 100)
