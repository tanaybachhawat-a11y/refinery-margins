"""
Step 3 - Crack spread analysis, refinery margin model and hedging backtest.
Runs the SQL in /sql against data/refinery.db, makes the charts in
outputs/charts and the Tableau-ready tables in outputs/tableau.

Usage:  python src/analysis.py
"""
import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import hedge_backtest as hb
import margin_model as mm

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "refinery.db"
SQL = ROOT / "sql"
CHARTS = ROOT / "outputs" / "charts"
TABLEAU = ROOT / "outputs" / "tableau"
for p in (CHARTS, TABLEAU):
    p.mkdir(parents=True, exist_ok=True)

LAST_FULL_MONTH = "2026-10"   # November 2026 is incomplete at time of writing
BACKTEST_START = "2010-01"    # leaves 3+ years of history for the opportunistic rule

# ---- chart style --------------------------------------------------------
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": INK2, "ytick.color": INK2, "legend.frameon": False,
    "figure.dpi": 150, "savefig.bbox": "tight", "lines.linewidth": 1.6, "axes.axisbelow": True,
})
EVENTS = [
    ("2008-09-15", "Financial\ncrisis"),
    ("2014-11-27", "OPEC price\nwar"),
    ("2020-03-11", "COVID"),
    ("2022-02-24", "Russia\ninvades\nUkraine"),
    ("2026-02-28", "Iran war /\nHormuz"),
]


def q(con, name: str) -> pd.DataFrame:
    return pd.read_sql((SQL / name).read_text(), con)


def annotate_events(ax, y, start=None):
    for d, label in EVENTS:
        x = pd.Timestamp(d)
        if start is not None and x < pd.Timestamp(start):
            continue
        ax.axvline(x, color=INK2, lw=0.8, ls=":", zorder=0)
        ax.text(x, y, " " + label, fontsize=7.5, color=INK2, va="top")


def save(fig, name):
    fig.savefig(CHARTS / name)
    plt.close(fig)


def main() -> None:
    con = sqlite3.connect(DB)
    daily = pd.read_sql("SELECT * FROM v_daily_cracks ORDER BY date", con,
                        parse_dates=["date"]).set_index("date")
    monthly = pd.read_sql("SELECT * FROM v_monthly_cracks ORDER BY month", con)
    monthly["month"] = pd.PeriodIndex(monthly["month"], freq="M").to_timestamp()
    monthly = monthly.set_index("month").loc[:LAST_FULL_MONTH]
    annual = q(con, "02_annual_summary.sql")
    annual["std_crack_321"] = np.sqrt(annual.pop("var_crack_321")).round(2)
    seasonal = q(con, "03_seasonality.sql")
    extremes = q(con, "04_extreme_months.sql")
    regimes = q(con, "05_regimes.sql")
    con.close()

    results = {}
    full = monthly.loc["2007":"2025"]
    results["avg_crack_2007_2025"] = full["crack_321_brent"].mean()
    results["avg_crack_2026_ytd"] = monthly.loc["2026", "crack_321_brent"].mean()
    results["peak_daily_crack"] = {"date": str(daily["crack_321_brent"].idxmax().date()),
                                   "value": daily["crack_321_brent"].max()}
    results["latest_month"] = monthly.iloc[-1][["brent", "crack_321_brent", "gasoline_crack",
                                                "diesel_crack", "brent_wti_spread"]].to_dict()

    # ------------------------------------------------------------------ #
    # Chart 1: 3-2-1 crack history with events
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(daily.index, daily["crack_321_brent"], color=BLUE, lw=0.6, alpha=0.35,
            label="Daily")
    ax.plot(monthly.index + pd.offsets.Day(14), monthly["crack_321_brent"], color=BLUE,
            lw=1.8, label="Monthly average")
    ax.axhline(results["avg_crack_2007_2025"], color=INK2, lw=1, ls="--")
    ax.text(daily.index[-1] + pd.Timedelta(days=60), results["avg_crack_2007_2025"],
            f"2007-25\naverage\n${results['avg_crack_2007_2025']:.0f}/bbl", fontsize=8,
            color=INK2, va="center")
    annotate_events(ax, daily["crack_321_brent"].max() * 1.02)
    ax.set_title("Brent 3-2-1 crack spread, NY Harbor products (USD per barrel)")
    ax.set_ylabel("USD/bbl")
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.88))
    save(fig, "01_crack_321_history.png")

    # ------------------------------------------------------------------ #
    # Chart 2: gasoline vs diesel cracks (monthly)
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(monthly.index, monthly["diesel_crack"], color=ORANGE, label="Diesel crack")
    ax.plot(monthly.index, monthly["gasoline_crack"], color=BLUE, label="Gasoline crack")
    ax.axhline(0, color=INK2, lw=0.8)
    annotate_events(ax, monthly["diesel_crack"].max() * 1.03)
    ax.set_title("Diesel has out-earned gasoline since 2022 (monthly average, USD per barrel over Brent)")
    ax.set_ylabel("USD/bbl")
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.88))
    last = monthly.iloc[-1]
    ax.annotate(f"${last.diesel_crack:.0f}", (monthly.index[-1], last.diesel_crack),
                xytext=(4, 0), textcoords="offset points", fontsize=8, color=INK)
    ax.annotate(f"${last.gasoline_crack:.0f}", (monthly.index[-1], last.gasoline_crack),
                xytext=(4, 0), textcoords="offset points", fontsize=8, color=INK)
    save(fig, "02_gasoline_vs_diesel.png")

    # ------------------------------------------------------------------ #
    # Chart 3: seasonality
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(8, 3.8))
    x = np.arange(1, 13)
    w = 0.38
    ax.bar(x - w / 2 - 0.01, seasonal["gasoline_vs_year_avg"], w, color=BLUE, label="Gasoline crack")
    ax.bar(x + w / 2 + 0.01, seasonal["diesel_vs_year_avg"], w, color=ORANGE, label="Diesel crack")
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(x, ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_title("Seasonality: gasoline peaks in spring and summer, diesel in late autumn and winter")
    ax.set_ylabel("USD/bbl vs that year's average")
    ax.text(0.5, -0.17, "Average 2007-2025, excluding the 2022 shock year. Each month measured against its own year's average.",
            transform=ax.transAxes, ha="center", fontsize=8, color=INK2)
    ax.legend(loc="upper right")
    save(fig, "03_seasonality.png")

    # ------------------------------------------------------------------ #
    # Chart 4: volatility (rolling 60-day std dev of daily crack changes)
    # ------------------------------------------------------------------ #
    vol = daily["crack_321_brent"].diff().rolling(60).std() * np.sqrt(252)
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.plot(vol.index, vol, color=BLUE)
    annotate_events(ax, vol.max() * 1.03)
    ax.set_title("Crack spread volatility (60-day rolling, annualised USD/bbl)")
    ax.set_ylabel("USD/bbl")
    save(fig, "04_volatility.png")
    results["vol_median"] = vol.median()
    results["vol_2026_peak"] = vol.loc["2026"].max()

    # ------------------------------------------------------------------ #
    # Chart 5: Brent-WTI spread
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.plot(monthly.index, monthly["brent_wti_spread"], color=AQUA)
    ax.axhline(0, color=INK2, lw=0.8)
    annotate_events(ax, monthly["brent_wti_spread"].max() * 1.05)
    ax.set_title("Brent minus WTI (monthly average, USD per barrel)")
    ax.set_ylabel("USD/bbl")
    save(fig, "05_brent_wti_spread.png")

    # ------------------------------------------------------------------ #
    # Refinery margin model + yield flexibility
    # ------------------------------------------------------------------ #
    flex = mm.yield_flexibility(monthly)
    flex_bt = flex.loc["2007":]
    base_mean = flex_bt[mm.BASE.name].mean()
    flex_gain = (flex_bt["Flexible (switches monthly)"] - flex_bt[mm.BASE.name]).mean()
    flex_gain_recent = (flex.loc["2022":, "Flexible (switches monthly)"]
                        - flex.loc["2022":, mm.BASE.name]).mean()
    results["model_base_net_margin_avg"] = base_mean
    results["model_base_net_margin_2026"] = flex.loc["2026", mm.BASE.name].mean()
    results["model_negative_months_pct"] = 100 * (flex_bt[mm.BASE.name] < 0).mean()
    results["flex_gain_per_bbl_2007_2026"] = flex_gain
    results["flex_gain_per_bbl_2022_2026"] = flex_gain_recent
    results["flex_gain_usd_m_per_year"] = mm.annual_value(flex_gain) / 1e6
    results["flex_gain_usd_m_per_year_2022_2026"] = mm.annual_value(flex_gain_recent) / 1e6
    results["pct_months_diesel_mode"] = 100 * (flex_bt["mode_chosen"] == "diesel").mean()
    results["base_margin_usd_m_per_year"] = mm.annual_value(base_mean) / 1e6

    annual_margin = flex.loc["2007":, mm.BASE.name].groupby(flex.loc["2007":].index.year).mean()
    fig, ax = plt.subplots(figsize=(10, 3.8))
    colors = [ORANGE if v < 0 else BLUE for v in annual_margin]
    ax.bar(annual_margin.index, annual_margin.values, color=colors, width=0.7)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(range(2007, 2027, 2))
    ax.set_title("Modelled net margin, diesel-oriented NW European refinery (USD/bbl, annual average)")
    ax.set_ylabel("USD/bbl")
    for yr, v in annual_margin.items():
        ax.text(yr, v + (0.6 if v >= 0 else -0.6), f"{v:.0f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=7.5, color=INK2)
    ax.text(0.0, -0.16, "2026 = January to October. Yields and costs are illustrative assumptions (see margin_model.py).",
            transform=ax.transAxes, fontsize=8, color=INK2)
    save(fig, "06_modelled_net_margin.png")

    # ------------------------------------------------------------------ #
    # Hedging backtest
    # ------------------------------------------------------------------ #
    strat = hb.run_strategies(monthly["crack_321_brent"]).loc[BACKTEST_START:]
    net_unhedged = mm.net_margin(monthly, mm.BASE).loc[BACKTEST_START:]
    summary = hb.summarise(strat, net_unhedged, monthly["crack_321_brent"])
    pnl = hb.hedge_pnl_by_year(strat, "50% hedge, 3 months ahead")
    results["hedge_summary"] = summary.round(2).reset_index().to_dict(orient="records")
    results["hedge_pnl_50pct_3m_by_year_usd_m"] = pnl.round(0).to_dict()

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(strat.index, strat["Unhedged"], color=BLUE, label="Unhedged", lw=1.4)
    ax.plot(strat.index, strat["50% hedge, 3 months ahead"], color=ORANGE,
            label="50% hedged, 3 months ahead", lw=1.4)
    annotate_events(ax, strat["Unhedged"].max() * 1.03, start=BACKTEST_START)
    ax.set_title("Hedging smooths margins but gives up the spikes (Brent 3-2-1, USD/bbl)")
    ax.set_ylabel("USD/bbl")
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.88))
    save(fig, "07_hedged_vs_unhedged.png")

    plot_order = ["Unhedged", "50% hedge, 3 months ahead", "50% layered (1/3 each month)",
                  "50% annual budget hedge", "100% hedge, 3 months ahead",
                  "Opportunistic (lock only when high)"]
    sm = summary.loc[plot_order]
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9), sharey=True)
    ylab = [s.replace(" (", "\n(").replace(", ", ",\n", 1) if len(s) > 22 else s for s in plot_order]
    panels = [("planning_surprise_std", "Surprise vs 3 months earlier\n(std dev, USD/bbl)", BLUE, "{:.1f}"),
              ("std_dev", "Overall volatility\n(std dev, USD/bbl)", BLUE, "{:.1f}"),
              ("avg_cost_vs_unhedged", "Average margin vs unhedged\n(USD/bbl)", None, "{:+.2f}")]
    for a, (col, title, color, fmt) in zip(axes, panels):
        vals = sm[col]
        cols_ = color or [ORANGE if v < 0 else AQUA for v in vals]
        a.barh(ylab, vals, color=cols_, height=0.6)
        a.set_title(title, fontsize=10)
        a.axvline(0, color=INK2, lw=0.8)
        span = vals.abs().max()
        for i, v in enumerate(vals):
            a.text(v + (0.02 * span if v >= 0 else -0.02 * span), i, fmt.format(v), va="center",
                   ha="left" if v >= 0 else "right", fontsize=8, color=INK2)
        a.grid(axis="y", visible=False)
        a.tick_params(axis="y", length=0)
        a.margins(x=0.18)
    axes[0].invert_yaxis()
    fig.suptitle(f"Hedging trade-off, {BACKTEST_START[:4]}-2026 (Brent 3-2-1, monthly)", x=0.01, ha="left",
                 fontweight="bold", fontsize=12, y=1.04)
    save(fig, "08_hedge_tradeoff.png")

    # ------------------------------------------------------------------ #
    # Tableau-ready exports (tidy CSVs)
    # ------------------------------------------------------------------ #
    daily.round(3).reset_index().to_csv(TABLEAU / "daily_cracks.csv", index=False)
    m_out = monthly.join(flex.drop(columns="mode_chosen").add_prefix("model_")).round(3)
    m_out.reset_index().to_csv(TABLEAU / "monthly_cracks_and_model.csv", index=False)
    strat_long = (strat.drop(columns="opportunistic_hedged").reset_index()
                  .melt(id_vars="month", var_name="strategy", value_name="margin_usd_bbl"))
    strat_long.round({"margin_usd_bbl": 3}).to_csv(TABLEAU / "hedge_backtest_long.csv", index=False)
    summary.round(3).to_csv(TABLEAU / "hedge_summary.csv")
    seasonal.to_csv(TABLEAU / "seasonality.csv", index=False)
    annual.to_csv(TABLEAU / "annual_summary.csv", index=False)
    regimes.to_csv(TABLEAU / "regimes.csv", index=False)
    extremes.to_csv(TABLEAU / "extreme_months.csv", index=False)

    with open(ROOT / "outputs" / "key_results.json", "w") as f:
        json.dump(results, f, indent=2, default=float)

    # ---- console report -------------------------------------------------
    pd.set_option("display.width", 160)
    print("\nREGIMES\n", regimes.to_string(index=False))
    print("\nANNUAL\n", annual.to_string(index=False))
    print("\nSEASONALITY\n", seasonal.to_string(index=False))
    print("\nEXTREMES\n", extremes.to_string(index=False))
    print("\nHEDGE SUMMARY\n", summary.round(2).to_string())
    print("\nHEDGE P&L 50%/3m by year (USD m, annualised)\n", pnl.round(0).to_string())
    print("\nKEY RESULTS\n", json.dumps({k: v for k, v in results.items()
                                          if k not in ("hedge_summary", "hedge_pnl_50pct_3m_by_year_usd_m")},
                                         indent=1, default=float))


if __name__ == "__main__":
    main()
