"""
Step 4 - Hedging backtest.

Question: how much does hedging reduce the volatility of a refiner's margin,
and what does it cost?

A refiner "sells the crack forward": it agrees today to sell products and buy
crude for a future month at today's spread (in practice via crack spread swaps
or by selling RBOB/heating-oil futures and buying Brent futures). If the spread
later falls, the hedge pays out; if it rises, the hedge loses money.

Per barrel, for a hedge ratio h:
    hedged margin = realised crack + h x (locked crack - realised crack)

KEY SIMPLIFICATION: free data has no historical forward curves, so the price
locked in for month M is the spot crack observed when the hedge is placed
(e.g. the average of month M-3). Real forward cracks differ from spot - in a
backwardated market such as 2022 or 2026, forwards sit BELOW spot, so this
backtest overstates the price a hedger could have locked in during those
spikes. Results show the direction and scale of the trade-off, not exact P&L.
"""
import numpy as np
import pandas as pd

from margin_model import BASE, annual_value


def locked_price(crack: pd.Series, lag: int) -> pd.Series:
    """Spot-as-forward: the crack observed `lag` months before delivery."""
    return crack.shift(lag)


def run_strategies(crack: pd.Series) -> pd.DataFrame:
    """Return a DataFrame of monthly margins (USD/bbl) for each strategy."""
    s = pd.DataFrame(index=crack.index)
    s["Unhedged"] = crack

    # 1. Rolling 3-month hedge: each month, lock 50% of the month 3 ahead.
    lock3 = locked_price(crack, 3)
    s["50% hedge, 3 months ahead"] = crack + 0.5 * (lock3 - crack)
    s["100% hedge, 3 months ahead"] = crack + 1.0 * (lock3 - crack)

    # 2. Layered hedge: 1/3 of the 50% placed in each of the 3 prior months,
    #    so the locked price is the average of months M-1, M-2, M-3.
    layered = (crack.shift(1) + crack.shift(2) + crack.shift(3)) / 3
    s["50% layered (1/3 each month)"] = crack + 0.5 * (layered - crack)

    # 3. Annual budget hedge: every December, lock 50% of all 12 months of the
    #    next year at December's crack (how many refiners set budgets).
    dec = crack[crack.index.month == 12]
    budget = pd.Series(np.nan, index=crack.index)
    for d, v in dec.items():
        budget[(budget.index.year == d.year + 1)] = v
    s["50% annual budget hedge"] = crack + 0.5 * (budget - crack)

    # 4. Opportunistic: lock 100% of month M only if, at M-3, the crack was in
    #    the top 30% of the previous 36 months (uses only past data).
    thresh = crack.rolling(36).quantile(0.70)
    trigger = (crack >= thresh).shift(3).fillna(False).astype(bool)
    s["Opportunistic (lock only when high)"] = np.where(trigger, lock3, crack)
    s["opportunistic_hedged"] = trigger
    return s


def summarise(s: pd.DataFrame, net_unhedged: pd.Series, full_crack: pd.Series) -> pd.DataFrame:
    """
    s            strategy margins on the crack (USD/bbl), backtest window only
    net_unhedged modelled refinery net margin (margin_model.net_margin), same index
    full_crack   the whole crack history (so the 3-month-ago value exists at the start)

    Two kinds of risk are measured:
      * std_dev - how much the margin swings over the whole period. A hedge
        only 3 months long cannot remove multi-year regime shifts, so this
        falls only modestly.
      * planning_surprise_std - how far the margin lands from what the
        refiner could see 3 months earlier (the crack at M-3). This is the
        uncertainty a hedge is actually bought to remove.
    """
    cols = [c for c in s.columns if c != "opportunistic_hedged"]
    base_std = s["Unhedged"].std()
    base_mean = s["Unhedged"].mean()
    seen_3m_earlier = full_crack.shift(3).reindex(s.index)
    rows = []
    for c in cols:
        x = s[c]
        net = net_unhedged + (x - s["Unhedged"])   # hedge P&L added to refinery margin
        surprise = x - seen_3m_earlier
        rows.append({
            "strategy": c,
            "mean_margin": x.mean(),
            "std_dev": x.std(),
            "volatility_reduction_pct": 100 * (1 - x.std() / base_std),
            "planning_surprise_std": surprise.std(),
            "worst_month": x.min(),
            "p5_month": x.quantile(0.05),
            "months_net_margin_negative": int((net < 0).sum()),
            "worst_12m_net_margin": net.rolling(12).mean().min(),
            "avg_cost_vs_unhedged": x.mean() - base_mean,
            "annual_cost_vs_unhedged_usd_m": annual_value(x.mean() - base_mean) / 1e6,
        })
    out = pd.DataFrame(rows).set_index("strategy")
    out["planning_surprise_reduction_pct"] = 100 * (
        1 - out["planning_surprise_std"] / out.loc["Unhedged", "planning_surprise_std"])
    return out


def hedge_pnl_by_year(s: pd.DataFrame, col: str) -> pd.Series:
    """Hedge gain/loss per year in USD millions at the refinery's run rate."""
    per_bbl = (s[col] - s["Unhedged"]).groupby(s.index.year).mean()
    return per_bbl.apply(annual_value) / 1e6
