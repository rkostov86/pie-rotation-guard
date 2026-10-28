"""Download prices (Yahoo via yfinance) and macro series (FRED CSV, no key)."""
import io
import time

import pandas as pd
import requests

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"


def _naive(idx):
    idx = pd.to_datetime(idx)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def fetch_prices(tickers, start="2000-01-01", retries=3):
    import yfinance as yf

    frames = {}
    for t in tickers:
        last_err = None
        for attempt in range(retries):
            try:
                hist = yf.Ticker(t).history(start=start, auto_adjust=True)
                s = hist["Close"].dropna()
                if len(s) < 50:
                    raise ValueError(f"only {len(s)} rows for {t}")
                s.index = _naive(s.index)
                frames[t] = s[~s.index.duplicated(keep="last")]
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"price download failed for {t}: {last_err}")
    px = pd.DataFrame(frames)
    # Master calendar = US trading days (SPY). FX trades on other days -> forward fill.
    px = px[px["SPY"].notna()].copy()
    if "EURUSD=X" in px:
        fx = frames["EURUSD=X"].reindex(px.index.union(frames["EURUSD=X"].index)).ffill()
        px["EURUSD=X"] = fx.reindex(px.index)
    return px


def fetch_fred(series, retries=3):
    out = {}
    for sid in series:
        last_err = None
        for attempt in range(retries):
            try:
                r = requests.get(FRED_URL.format(sid=sid), timeout=60,
                                 headers={"User-Agent": "pie-rotation-guard/1.0"})
                r.raise_for_status()
                df = pd.read_csv(io.StringIO(r.text), na_values=["."])
                s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                              index=_naive(df.iloc[:, 0]), name=sid).dropna()
                if len(s) < 50:
                    raise ValueError(f"only {len(s)} rows for {sid}")
                out[sid] = s
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"FRED download failed for {sid}: {last_err}")
    return out


def align_to(series, index, limit=5):
    """Forward-fill a daily macro series onto the trading calendar (max `limit` days stale)."""
    u = series.reindex(series.index.union(index)).ffill(limit=limit)
    return u.reindex(index)
