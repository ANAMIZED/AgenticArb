"""
ADL Rank Estimator
==================
Heuristic estimator of Auto-Deleveraging rank on Hyperliquid-style venues.
Prefers positions that stay out of the early force-close queue.

Public data is limited; we use leverage + relative unrealized PnL ranking
as a proxy (higher leverage + higher profit → earlier in ADL queue on many venues).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


@dataclass
class PositionSnapshot:
    asset: str
    side: str               # "long" | "short"
    notional: float
    leverage: float
    unrealized_pnl: float   # absolute USD
    entry_price: float
    mark_price: float
    account_equity: float


@dataclass
class ADLEstimate:
    estimated_rank_percentile: float   # 0 = first to be ADLd, 1 = last
    risk_score: float                  # higher = more dangerous
    prefer_keep: bool
    recommendation: str
    diagnostics: Dict


class ADLRankEstimator:
    """
    Simple but effective heuristic.
    In production this would ingest any available public ranking or
    inferred from observed ADL events.
    """

    def __init__(self, max_safe_leverage: float = 8.0):
        self.max_safe_leverage = max_safe_leverage

    def estimate(self, pos: PositionSnapshot, market_avg_leverage: float = 4.0) -> ADLEstimate:
        # Profit rank proxy: higher positive PnL relative to equity → earlier ADL
        pnl_ratio = pos.unrealized_pnl / max(pos.account_equity, 1.0)
        # Leverage rank
        lev_score = pos.leverage / max(market_avg_leverage, 1.0)

        # Combined "early ADL" score (higher = more likely early)
        early_score = 0.55 * max(pnl_ratio, 0.0) + 0.45 * lev_score
        # Convert to percentile (rough)
        rank_pct = 1.0 / (1.0 + np.exp(3.0 * (early_score - 0.8)))  # sigmoid

        risk_score = early_score * (1.0 + 0.3 * (pos.leverage / self.max_safe_leverage))

        prefer = rank_pct > 0.35 and pos.leverage < self.max_safe_leverage
        if not prefer:
            rec = "REDUCE_OR_HEDGE – elevated ADL risk"
        elif rank_pct > 0.7:
            rec = "KEEP – low ADL priority"
        else:
            rec = "MONITOR – mid queue"

        return ADLEstimate(
            estimated_rank_percentile=float(np.clip(rank_pct, 0.01, 0.99)),
            risk_score=float(risk_score),
            prefer_keep=prefer,
            recommendation=rec,
            diagnostics={
                "pnl_ratio": pnl_ratio,
                "lev_score": lev_score,
                "early_score": early_score,
            },
        )

    def batch_rank(self, positions: List[PositionSnapshot]) -> List[ADLEstimate]:
        return [self.estimate(p) for p in positions]
