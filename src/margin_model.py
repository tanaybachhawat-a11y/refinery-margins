"""
Yield-based refinery margin model.

A crack spread is a market indicator; a real refinery's margin depends on what
its units actually produce. This module values a refinery's product slate
(its "yield") at market prices to estimate gross and net margin per barrel.

All parameters are ILLUSTRATIVE assumptions for a diesel-oriented, complex
North-West European refinery of Fawley's scale (~270,000 bbl/day). They are
not ExxonMobil data. Change them in CONFIG to test other configurations.
"""
from dataclasses import dataclass

import pandas as pd


@dataclass
class RefineryConfig:
    name: str
    gasoline_yield: float   # fraction of crude volume -> gasoline (incl. reformate, FCC gasoline)
    distillate_yield: float # -> diesel + jet + gasoil (valued at ULSD)
    other_yield: float      # -> LPG, naphtha, fuel oil, bitumen, petchem feeds
    other_value_vs_crude: float  # "other" products valued at this fraction of Brent
    fuel_and_loss: float    # crude burned as refinery fuel or lost (zero value)
    variable_opex: float    # USD/bbl: utilities, chemicals, catalysts, maintenance
    capacity_bpd: float = 270_000
    utilisation: float = 0.90

    def check(self) -> None:
        total = self.gasoline_yield + self.distillate_yield + self.other_yield + self.fuel_and_loss
        assert abs(total - 1.0) < 1e-9, f"{self.name}: yields sum to {total:.3f}, not 1"


# Base case plus the two operating "modes" a refinery can lean towards by
# changing cut points on the crude unit and the severity of the FCC / hydrocracker.
BASE = RefineryConfig("Base case", 0.28, 0.44, 0.24, 0.90, 0.04, 4.0)
MAX_DIESEL = RefineryConfig("Max-diesel mode", 0.24, 0.48, 0.24, 0.90, 0.04, 4.0)
MAX_GASOLINE = RefineryConfig("Max-gasoline mode", 0.32, 0.40, 0.24, 0.90, 0.04, 4.0)
CONFIGS = [BASE, MAX_DIESEL, MAX_GASOLINE]


def gross_product_worth(df: pd.DataFrame, cfg: RefineryConfig) -> pd.Series:
    """Value of the products made from one barrel of crude (USD/bbl)."""
    cfg.check()
    return (cfg.gasoline_yield * df["gasoline"]
            + cfg.distillate_yield * df["diesel"]
            + cfg.other_yield * cfg.other_value_vs_crude * df["brent"])


def net_margin(df: pd.DataFrame, cfg: RefineryConfig) -> pd.Series:
    """Gross product worth minus crude cost minus variable opex (USD/bbl)."""
    return gross_product_worth(df, cfg) - df["brent"] - cfg.variable_opex


def annual_value(usd_per_bbl: float, cfg: RefineryConfig = BASE) -> float:
    """Convert a USD/bbl figure into USD per year at the refinery's run rate."""
    return usd_per_bbl * cfg.capacity_bpd * cfg.utilisation * 365


def yield_flexibility(monthly: pd.DataFrame) -> pd.DataFrame:
    """
    Value of being able to switch between max-diesel and max-gasoline modes.
    Each month the refinery picks the mode with the higher margin, using the
    PREVIOUS month's prices to decide (no hindsight), then earns this month's.
    """
    out = pd.DataFrame(index=monthly.index)
    for cfg in CONFIGS:
        out[cfg.name] = net_margin(monthly, cfg)
    pick_diesel = (out[MAX_DIESEL.name] >= out[MAX_GASOLINE.name]).shift(1)
    out["Flexible (switches monthly)"] = out[MAX_DIESEL.name].where(
        pick_diesel.fillna(True).astype(bool), out[MAX_GASOLINE.name])
    out["mode_chosen"] = pick_diesel.map({True: "diesel", False: "gasoline"})
    return out
