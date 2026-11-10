"""Rebuild everything: database -> analysis -> charts -> Tableau CSVs.

    python run_all.py            # uses the CSV already in data/raw
    python run_all.py --fetch    # re-downloads prices from FRED first (needs FRED_API_KEY)
"""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"

steps = (["fetch_data.py"] if "--fetch" in sys.argv else []) + ["build_db.py", "analysis.py"]
for step in steps:
    print(f"\n=== {step} ===")
    subprocess.run([sys.executable, step], cwd=SRC, check=True)
