"""
Step 1 - Download daily spot prices from FRED (Federal Reserve Bank of St. Louis),
which republishes the U.S. Energy Information Administration (EIA) spot price series.

Series used
-----------
DCOILBRENTEU  Brent crude, Europe               USD per barrel
DCOILWTICO    WTI crude, Cushing Oklahoma       USD per barrel
DGASNYH       Conventional gasoline, NY Harbor  USD per gallon
DDFUELNYH     Ultra-low-sulphur diesel, NY Harbor USD per gallon

Usage
-----
    export FRED_API_KEY=your_key      # free at https://fred.stlouisfed.org/docs/api/api_key.html
    python src/fetch_data.py

Output: data/raw/fred_prices_daily.csv  (long format: date, series_id, value)
"""
import os
import sys
from pathlib import Path

import pandas as pd
import requests

SERIES = ["DCOILBRENTEU", "DCOILWTICO", "DGASNYH", "DDFUELNYH"]
START = "2006-07-01"  # NY Harbor ULSD series starts mid-2006
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "fred_prices_daily.csv"
URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series(series_id: str, api_key: str) -> pd.DataFrame:
    params = {
        "series_id": series_id,
        "observation_start": START,
        "api_key": api_key,
        "file_type": "json",
    }
    r = requests.get(URL, params=params, timeout=60)
    r.raise_for_status()
    obs = pd.DataFrame(r.json()["observations"])[["date", "value"]]
    # FRED marks missing days (holidays) with "."
    obs = obs[obs["value"] != "."].copy()
    obs["value"] = obs["value"].astype(float)
    obs["series_id"] = series_id
    return obs[["date", "series_id", "value"]]


def main() -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        sys.exit("Set FRED_API_KEY first (free key from fred.stlouisfed.org).")
    frames = [fetch_series(s, api_key) for s in SERIES]
    df = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Saved {len(df):,} rows to {OUT}")
    print(df.groupby("series_id")["date"].agg(["min", "max", "count"]))


if __name__ == "__main__":
    main()
