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


FRED_API = "https://api.stlouisfed.org/fred/series/observations"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) pie-rotation-guard/1.0", "Accept": "text/csv,*/*"}


def _fred_csv(sid, start):
    """FRED stalls Python's HTTP client from GitHub runners but answers curl instantly, so use curl."""
    import shutil
    import subprocess

    url = FRED_URL.format(sid=sid) + f"&cosd={start}"
    if shutil.which("curl"):
        p = subprocess.run(["curl", "-sS", "-f", "-m", "90", "--retry", "2", url],
                           capture_output=True, text=True, timeout=200)
        if p.returncode != 0:
            raise RuntimeError(f"curl exit {p.returncode}: {p.stderr.strip()[:200]}")
        text = p.stdout
    else:
        r = requests.get(url, timeout=(20, 180), headers=UA)
        r.raise_for_status()
        text = r.text
    df = pd.read_csv(io.StringIO(text), na_values=["."])
    return pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                     index=_naive(df.iloc[:, 0]), name=sid).dropna()


def _fred_api(sid, start, key):
    r = requests.get(FRED_API, timeout=(20, 120), headers=UA, params={
        "series_id": sid, "api_key": key, "file_type": "json", "observation_start": start})
    r.raise_for_status()
    obs = r.json()["observations"]
    s = pd.Series([o["value"] for o in obs], index=_naive([o["date"] for o in obs]), name=sid)
    return pd.to_numeric(s.replace(".", None), errors="coerce").dropna()


def fetch_fred(series, start="1999-01-01", retries=4):
    """FRED CSV endpoint first; the official API if FRED_API_KEY is set (more reliable from CI)."""
    import os
    key = os.environ.get("FRED_API_KEY")
    out = {}
    for sid in series:
        errs = []
        methods = ([("api", lambda: _fred_api(sid, start, key))] if key else []) + [("csv", lambda: _fred_csv(sid, start))]
        for attempt in range(retries):
            name, fn = methods[attempt % len(methods)]
            try:
                s = fn()
                if len(s) < 50:
                    raise ValueError(f"only {len(s)} rows")
                out[sid] = s
                break
            except Exception as e:  # noqa: BLE001
                errs.append(f"{name}: {e!r}")
                time.sleep(10 * (attempt + 1))
        else:
            raise RuntimeError(f"FRED download failed for {sid}: " + " | ".join(errs))
    return out


def align_to(series, index, limit=5):
    """Forward-fill a daily macro series onto the trading calendar (max `limit` days stale)."""
    u = series.reindex(series.index.union(index)).ffill(limit=limit)
    return u.reindex(index)
