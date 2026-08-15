"""
L2 Impact & Dynamic Capacity Model
==================================
Temporary + permanent impact curves (power-law / Almgren-Chriss inspired)
calibrated on Hyperliquid L2 depth characteristics.

Capacity = maximum notional such that expected impact < half the expected
net funding edge. Dynamic degradation as own OI share or recent arb volume rises.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np


@dataclass
class ImpactParams:
    # Temporary impact: η * (Q / V)^α
    temp_eta: float = 0.0008
    temp_alpha: float = 0.6
    # Permanent impact: γ * (Q / ADV)
    perm_gamma: float = 0.0003
    # Depth proxy (USD notional within 10 bps)
    typical_depth_10bps: float = 250_000.0
    # ADV proxy
    typical_adv: float = 5_000_000.0


# Rough calibration per asset class on HL (can be live-updated from L2)
ASSET_IMPACT: Dict[str, ImpactParams] = {
    "BTC": ImpactParams(temp_eta=0.0004, typical_depth_10bps=2_000_000, typical_adv=80_000_000),
    "ETH": ImpactParams(temp_eta=0.0005, typical_depth_10bps=800_000, typical_adv=30_000_000),
    "TSLA": ImpactParams(temp_eta=0.0012, typical_depth_10bps=80_000, typical_adv=1_500_000),
    "NVDA": ImpactParams(temp_eta=0.0015, typical_depth_10bps=60_000, typical_adv=1_200_000),
    "GOLD": ImpactParams(temp_eta=0.0009, typical_depth_10bps=150_000, typical_adv=3_000_000),
    "CL": ImpactParams(temp_eta=0.0011, typical_depth_10bps=100_000, typical_adv=2_000_000),
    "DEFAULT": ImpactParams(),
}


@dataclass
class CapacityEstimate:
    max_notional: float
    expected_temp_impact_bps: float
    expected_perm_impact_bps: float
    total_impact_bps: float
    edge_consumption_ratio: float
    recommended_size: float
    degradation_factor: float
    diagnostics: Dict


class ImpactCapacityModel:
    """
    Computes temporary + permanent impact and derives capacity-aware size.
    """

    def __init__(self, own_oi_share: float = 0.0, recent_arb_volume_ratio: float = 0.0):
        self.own_oi_share = np.clip(own_oi_share, 0.0, 0.5)
        self.recent_arb_volume_ratio = np.clip(recent_arb_volume_ratio, 0.0, 2.0)

    def update_crowding(self, own_oi_share: float, recent_arb_volume_ratio: float) -> None:
        self.own_oi_share = np.clip(own_oi_share, 0.0, 0.5)
        self.recent_arb_volume_ratio = np.clip(recent_arb_volume_ratio, 0.0, 2.0)

    def _params(self, asset: str) -> ImpactParams:
        return ASSET_IMPACT.get(asset.upper(), ASSET_IMPACT["DEFAULT"])

    def expected_impact_bps(
        self,
        asset: str,
        notional: float,
        side: str = "sell",  # short perp to collect positive funding
    ) -> Tuple[float, float, float]:
        """
        Returns (temp_bps, perm_bps, total_bps)
        """
        p = self._params(asset)
        # Participation rate proxy
        part = notional / max(p.typical_depth_10bps, 1.0)
        temp = p.temp_eta * (part ** p.temp_alpha) * 10_000  # to bps
        perm = p.perm_gamma * (notional / max(p.typical_adv, 1.0)) * 10_000
        # Crowding penalty
        crowd = 1.0 + 1.5 * self.own_oi_share + 0.8 * self.recent_arb_volume_ratio
        total = (temp + perm) * crowd
        return float(temp), float(perm), float(total)

    def capacity_for_edge(
        self,
        asset: str,
        expected_net_edge_bps: float,   # expected funding edge over holding period, net of costs
        max_impact_fraction: float = 0.5,
        hard_cap_notional: float = 2_000_000.0,
    ) -> CapacityEstimate:
        """
        Find largest notional such that total_impact <= max_impact_fraction * edge.
        Uses binary search for stability.
        """
        if expected_net_edge_bps <= 0:
            return CapacityEstimate(
                max_notional=0.0,
                expected_temp_impact_bps=0.0,
                expected_perm_impact_bps=0.0,
                total_impact_bps=0.0,
                edge_consumption_ratio=1.0,
                recommended_size=0.0,
                degradation_factor=1.0,
                diagnostics={"reason": "non_positive_edge"},
            )

        target_impact = max_impact_fraction * expected_net_edge_bps
        lo, hi = 1_000.0, hard_cap_notional
        best = 0.0
        for _ in range(40):
            mid = (lo + hi) / 2
            _, _, imp = self.expected_impact_bps(asset, mid)
            if imp <= target_impact:
                best = mid
                lo = mid
            else:
                hi = mid

        temp, perm, total = self.expected_impact_bps(asset, best)
        degradation = 1.0 + 1.5 * self.own_oi_share + 0.8 * self.recent_arb_volume_ratio
        # Final recommended size also applies a safety haircut
        recommended = best * 0.85 / degradation

        return CapacityEstimate(
            max_notional=float(best),
            expected_temp_impact_bps=temp,
            expected_perm_impact_bps=perm,
            total_impact_bps=total,
            edge_consumption_ratio=float(total / max(expected_net_edge_bps, 1e-9)),
            recommended_size=float(max(0.0, recommended)),
            degradation_factor=float(degradation),
            diagnostics={
                "target_impact_bps": target_impact,
                "own_oi_share": self.own_oi_share,
                "arb_volume_ratio": self.recent_arb_volume_ratio,
            },
        )

    def size_from_edge_and_vol(
        self,
        asset: str,
        expected_edge_bps: float,
        realized_vol: float,
        risk_budget_usd: float,
        max_leverage: float = 5.0,
    ) -> float:
        """
        Inverse-vol + capacity-aware sizing.
        """
        cap = self.capacity_for_edge(asset, expected_edge_bps)
        # Risk-based size: risk_budget / (vol * notional_factor)
        vol_size = risk_budget_usd / max(realized_vol, 0.01)
        # Cap by leverage and capacity
        final = min(cap.recommended_size, vol_size, risk_budget_usd * max_leverage)
        return float(max(0.0, final))
