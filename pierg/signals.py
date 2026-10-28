"""The five rotation signals, computed for every trading day."""
import numpy as np
import pandas as pd

from . import config as C
from .data import align_to


def _vs_ma(ratio, days):
    ma = ratio.rolling(days, min_periods=days).mean()
    above = (ratio > ma).astype(float)
    above[ma.isna() | ratio.isna()] = np.nan
    dist = (ratio / ma - 1.0) * 100.0
    return above, dist


def pick_credit_series(fred, needed_from):
    """HY OAS if its history covers the test window, otherwise the declared Baa fallback."""
    hy = fred.get("BAMLH0A0HYM2")
    if hy is not None and len(hy) and hy.index[0] <= pd.Timestamp(needed_from):
        return "BAMLH0A0HYM2", C.HY_THRESHOLD
    return "BAA10Y", C.BAA_FALLBACK_THRESHOLD


def build(px, fred, credit_sid, credit_thr):
    idx = px.index
    s1, d1 = _vs_ma(px["RSP"] / px["SPY"], C.SMA_DAYS)
    s2, d2 = _vs_ma(px["IWD"] / px["IWF"], C.SMA_DAYS)
    above3, d3 = _vs_ma(px["SOXX"] / px["SPY"], C.SMA_DAYS)
    s3 = 1.0 - above3  # chips BELOW their average

    credit = align_to(fred[credit_sid], idx)
    low = credit.rolling(C.CREDIT_LOOKBACK_DAYS, min_periods=int(C.CREDIT_LOOKBACK_DAYS * 0.8)).min()
    widening = credit - low
    s4 = (widening >= credit_thr).astype(float)
    s4[widening.isna()] = np.nan

    y10 = align_to(fred["DGS10"], idx)
    s5 = (y10 >= C.YIELD_THRESHOLD).astype(float)
    s5[y10.isna()] = np.nan

    f = pd.DataFrame({"s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5,
                      "rsp_spy_vs_ma_pct": d1, "iwd_iwf_vs_ma_pct": d2, "soxx_spy_vs_ma_pct": d3,
                      "credit": credit, "credit_widening": widening, "y10": y10}, index=idx)
    sig = f[["s1", "s2", "s3", "s4", "s5"]]
    f["valid"] = sig.notna().all(axis=1)
    f["n"] = sig.sum(axis=1, min_count=5)
    return f
