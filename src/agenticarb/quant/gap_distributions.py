"""Asset-Specific Empirical Gap Distributions for RWA perps."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

@dataclass
class GapStats:
    mean: float
    std: float
    p95: float
    p99: float
    p05: float
    p01: float
    n_samples: int
    asset_class: str

EMPIRICAL_GAPS: Dict[str, GapStats] = {
    "TSLA": GapStats(0.002, 0.035, 0.055, 0.085, -0.050, -0.080, 120, "equity"),
    "AAPL": GapStats(0.001, 0.018, 0.028, 0.042, -0.025, -0.040, 150, "equity"),
    "NVDA": GapStats(0.003, 0.040, 0.065, 0.100, -0.055, -0.090, 100, "equity"),
    "SPX": GapStats(0.0005, 0.012, 0.018, 0.028, -0.016, -0.025, 200, "equity"),
    "GOLD": GapStats(0.000, 0.010, 0.015, 0.022, -0.014, -0.020, 180, "commodity"),
    "XAU": GapStats(0.000, 0.010, 0.015, 0.022, -0.014, -0.020, 180, "commodity"),
    "CL": GapStats(0.001, 0.025, 0.040, 0.060, -0.035, -0.055, 160, "commodity"),
    "WTI": GapStats(0.001, 0.025, 0.040, 0.060, -0.035, -0.055, 160, "commodity"),
    "EUR": GapStats(0.000, 0.006, 0.009, 0.014, -0.008, -0.012, 220, "fx"),
    "JPY": GapStats(0.000, 0.007, 0.011, 0.016, -0.010, -0.015, 220, "fx"),
    "BTC": GapStats(0.000, 0.015, 0.025, 0.040, -0.022, -0.035, 300, "crypto"),
    "ETH": GapStats(0.000, 0.020, 0.032, 0.050, -0.028, -0.045, 300, "crypto"),
}

class GapDistributionSampler:
    def __init__(self, seed: Optional[int] = 42):
        self.rng = np.random.default_rng(seed)
        self.custom: Dict[str, List[float]] = {}

    def get_stats(self, asset: str) -> GapStats:
        asset = asset.upper()
        if asset in EMPIRICAL_GAPS:
            return EMPIRICAL_GAPS[asset]
        return GapStats(0.0, 0.02, 0.03, 0.05, -0.03, -0.05, 50, "unknown")

    def sample_gap(self, asset: str, side: str = "adverse_short", method: str = "empirical_p", size: int = 1) -> np.ndarray:
        stats = self.get_stats(asset)
        if method == "empirical_p":
            if side == "adverse_short":
                vals = [stats.p95] if size == 1 else self.rng.choice([stats.p95, stats.p99], size=size, p=[0.8, 0.2])
            else:
                vals = [stats.p05] if size == 1 else self.rng.choice([stats.p05, stats.p01], size=size, p=[0.8, 0.2])
            return np.asarray(vals)
        samples = self.rng.normal(stats.mean, stats.std, size=size)
        return np.clip(samples, -0.20, 0.20)

    def stress_test_position(self, asset: str, side: str, notional: float, current_margin: float, leverage: float) -> Dict:
        adverse_side = "adverse_short" if side == "short" else "adverse_long"
        gap_95 = float(self.sample_gap(asset, adverse_side, method="empirical_p")[0])
        gap_99 = float(self.get_stats(asset).p99 if side == "short" else abs(self.get_stats(asset).p01))
        loss_95 = abs(gap_95) * notional
        loss_99 = abs(gap_99) * notional
        survives_95 = current_margin > loss_95 * 1.1
        survives_99 = current_margin > loss_99 * 1.2
        return {"gap_95": gap_95, "gap_99": gap_99, "loss_95": loss_95, "loss_99": loss_99, "survives_95": survives_95, "survives_99": survives_99, "buffer_needed_99": max(0.0, loss_99 * 1.2 - current_margin)}
