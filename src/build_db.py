"""
Step 2 - Load the raw CSV into a SQLite database and create the analysis views.

Usage:  python src/build_db.py
Output: data/refinery.db
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "fred_prices_daily.csv"
DB = ROOT / "data" / "refinery.db"
SCHEMA = ROOT / "sql" / "01_schema_and_views.sql"


def main() -> None:
    df = pd.read_csv(RAW)

    # --- basic data-quality checks before loading -------------------------
    assert df["value"].notna().all(), "missing values in raw file"
    dupes = df.duplicated(["date", "series_id"]).sum()
    assert dupes == 0, f"{dupes} duplicate date/series rows"
    # Non-positive prices: the only one should be WTI on 20 Apr 2020 (-$36.98),
    # when the expiring May contract went negative because Cushing storage was
    # nearly full. It is a real price, so it is kept and flagged, not deleted.
    neg = df[df["value"] <= 0]
    for _, r in neg.iterrows():
        print(f"Note: non-positive price kept - {r.date} {r.series_id} {r.value}")
    assert set(neg["series_id"]) <= {"DCOILWTICO"}, "unexpected non-positive price"

    with sqlite3.connect(DB) as con:
        con.executescript(SCHEMA.read_text())
        df.to_sql("prices", con, if_exists="append", index=False)
        n = con.execute("SELECT COUNT(*) FROM v_daily_cracks").fetchone()[0]
        first, last = con.execute("SELECT MIN(date), MAX(date) FROM v_daily_cracks").fetchone()
    print(f"Loaded {len(df):,} raw rows -> {n:,} complete trading days ({first} to {last})")


if __name__ == "__main__":
    main()
