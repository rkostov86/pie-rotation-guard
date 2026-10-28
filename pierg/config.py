"""All rule parameters in one place. Values were fixed BEFORE the backtest ran."""

# --- Signals -----------------------------------------------------------------
SMA_DAYS = 200                 # moving-average length for the three ratio signals
CREDIT_LOOKBACK_DAYS = 126     # ~6 months of trading days for the credit-spread low
HY_THRESHOLD = 1.00            # HY OAS widening vs 6-month low, percentage points (100bp)
BAA_FALLBACK_THRESHOLD = 0.50  # used only if HY OAS history is too short (declared up front)
YIELD_THRESHOLD = 5.9          # 10-year Treasury yield, %

SIGNAL_NAMES = {
    "s1": "Equal weight beating cap weight (RSP/SPY above 200d)",
    "s2": "Value beating growth (IWD/IWF above 200d)",
    "s3": "Chips lagging market (SOXX/SPY below 200d)",
    "s4": "Credit stress (spread >= threshold above 6-month low)",
    "s5": "10-year yield >= 5.9%",
}

# --- Rule --------------------------------------------------------------------
ENTER_MIN = 3   # Normal -> Rotation when at least this many signals are true...
EXIT_MAX = 1    # Rotation -> Normal when at most this many are true...
# ...for `confirm` consecutive checks.

VARIANTS = {
    "A": {"schedule": "monthly", "confirm": 2, "label": "Monthly, 2 checks (~2 months)"},
    "B": {"schedule": "semimonthly", "confirm": 2, "label": "1st & 15th, 2 checks (~4 weeks)"},
    "C": {"schedule": "semimonthly", "confirm": 4, "label": "1st & 15th, 4 checks (~2 months)"},
}

# Tuning round 1 (the ONE round allowed by the approved plan), declared 2026-10-28
# BEFORE its results were seen: original A/B/C failed on switch count, so each
# variant must hold its condition 50% longer. Nothing else changes.
TUNED_VARIANTS = {
    "A2": {"schedule": "monthly", "confirm": 3, "label": "Monthly, 3 checks (~3 months)"},
    "B2": {"schedule": "semimonthly", "confirm": 3, "label": "1st & 15th, 3 checks (~6 weeks)"},
    "C2": {"schedule": "semimonthly", "confirm": 6, "label": "1st & 15th, 6 checks (~3 months)"},
}

# --- Pie targets (real UCITS funds) -------------------------------------------
NORMAL = {"SXR8": 0.35, "XNAQ": 0.20, "IXUA": 0.20, "SPYD": 0.15, "XDEW": 0.10}
ROTATION = {"SXR8": 0.30, "XNAQ": 0.10, "IXUA": 0.25, "SPYD": 0.15, "XDEW": 0.10, "4GLD": 0.10}

# US-listed stand-ins used for the backtest (longer history)
PROXY = {"SXR8": "SPY", "XNAQ": "QQQ", "IXUA": "EFA", "SPYD": "SDY", "XDEW": "RSP", "4GLD": "GLD"}

SWITCH_COST = 0.001  # 0.1% of every euro traded at a switch (spread/slippage assumption)

# --- Pass criteria (approved by Rumba before results) ------------------------
MAX_SWITCHES = 6             # every mode change counts as one switch
FALSE_ALARM_DAYS = 92        # Rotation reversed within ~3 months = false alarm
MAX_FALSE_ALARMS = 2
MUST_CATCH = {               # must be in Rotation mode at some point inside these declines
    "2008": ("2007-10-09", "2009-03-09"),
    "2022": ("2022-01-03", "2022-10-12"),
}

PRICE_TICKERS = ["SPY", "RSP", "IWD", "IWF", "SOXX", "QQQ", "EFA", "SDY", "GLD", "EURUSD=X"]
FRED_SERIES = ["DGS10", "BAMLH0A0HYM2", "BAA10Y"]
