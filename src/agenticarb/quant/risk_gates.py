"""
Formal Risk Gates
=================
Pure functions implementing hard risk constraints.
Designed so critical paths can be formally verified (or at least unit-tested
to high coverage). Every gate returns (allowed: bool, reason: str, metrics: dict).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from .gap_distributions import GapDistributionSampler
from .impact_capacity import ImpactCapacityModel, CapacityEstimate
from .funding_persistence import PersistencePrediction
from .adl_estimator import ADLEstimate


@dataclass
class ProposedTrade:
    asset: str
    side: str                 # "long" | "short"
    notional: float
    leverage: float
    expected_edge_bps: float
    holding_hours: float
    current_margin_buffer: float
    portfolio_notional: float
    portfolio_equity: float
    correlation_to_existing: float = 0.0
    own_oi_share: float = 0.0


@dataclass
class GateResult:
    allowed: bool
    gate_name: str
    reason: str
    metrics: Dict


class RiskGates:
    """
    Composition of pure risk checks. The final decision is the AND of all gates.
    """

    def __init__(
        self,
        max_leverage: float = 5.0,
        max_portfolio_concentration: float = 0.25,
        max_oi_share: float = 0.08,
        min_edge_after_impact_bps: float = 5.0,
        max_gap_loss_fraction: float = 0.35,
        max_correlation: float = 0.7,
    ):
        self.max_leverage = max_leverage
        self.max_concentration = max_portfolio_concentration
        self.max_oi_share = max_oi_share
        self.min_edge = min_edge_after_impact_bps
        self.max_gap_loss_frac = max_gap_loss_fraction
        self.max_corr = max_correlation
        self.gap_sampler = GapDistributionSampler()
        self.impact_model = ImpactCapacityModel()

    def gate_leverage(self, trade: ProposedTrade) -> GateResult:
        ok = trade.leverage <= self.max_leverage
        return GateResult(
            allowed=ok,
            gate_name="leverage",
            reason=f"leverage {trade.leverage:.2f} {'<=' if ok else '>'} {self.max_leverage}",
            metrics={"leverage": trade.leverage, "limit": self.max_leverage},
        )

    def gate_concentration(self, trade: ProposedTrade) -> GateResult:
        conc = trade.notional / max(trade.portfolio_equity, 1.0)
        ok = conc <= self.max_concentration
        return GateResult(
            allowed=ok,
            gate_name="concentration",
            reason=f"concentration {conc:.2%} {'<=' if ok else '>'} {self.max_concentration:.0%}",
            metrics={"concentration": conc, "limit": self.max_concentration},
        )

    def gate_oi_share(self, trade: ProposedTrade) -> GateResult:
        ok = trade.own_oi_share <= self.max_oi_share
        return GateResult(
            allowed=ok,
            gate_name="oi_share",
            reason=f"own OI share {trade.own_oi_share:.2%} {'<=' if ok else '>'} {self.max_oi_share:.0%}",
            metrics={"own_oi_share": trade.own_oi_share, "limit": self.max_oi_share},
        )

    def gate_gap_stress(self, trade: ProposedTrade) -> GateResult:
        stress = self.gap_sampler.stress_test_position(
            asset=trade.asset,
            side=trade.side,
            notional=trade.notional,
            current_margin=trade.current_margin_buffer,
            leverage=trade.leverage,
        )
        # Require survival of 95% gap with buffer
        loss_frac = stress["loss_95"] / max(trade.portfolio_equity, 1.0)
        ok = stress["survives_95"] and loss_frac <= self.max_gap_loss_frac
        return GateResult(
            allowed=ok,
            gate_name="gap_stress",
            reason=(
                f"95pct gap loss {loss_frac:.1%} of equity, survives={stress['survives_95']}"
            ),
            metrics=stress,
        )

    def gate_impact_vs_edge(self, trade: ProposedTrade) -> GateResult:
        self.impact_model.update_crowding(trade.own_oi_share, 0.0)
        cap: CapacityEstimate = self.impact_model.capacity_for_edge(
            trade.asset, trade.expected_edge_bps
        )
        remaining_edge = trade.expected_edge_bps - cap.total_impact_bps
        ok = remaining_edge >= self.min_edge and trade.notional <= cap.max_notional * 1.05
        return GateResult(
            allowed=ok,
            gate_name="impact_vs_edge",
            reason=(
                f"edge after impact {remaining_edge:.1f} bps "
                f"(min {self.min_edge}), size vs capacity {trade.notional:.0f}/{cap.max_notional:.0f}"
            ),
            metrics={
                "remaining_edge_bps": remaining_edge,
                "total_impact_bps": cap.total_impact_bps,
                "max_notional": cap.max_notional,
                "recommended": cap.recommended_size,
            },
        )

    def gate_correlation(self, trade: ProposedTrade) -> GateResult:
        ok = abs(trade.correlation_to_existing) <= self.max_corr
        return GateResult(
            allowed=ok,
            gate_name="correlation",
            reason=f"|corr| {abs(trade.correlation_to_existing):.2f} {'<=' if ok else '>'} {self.max_corr}",
            metrics={"correlation": trade.correlation_to_existing},
        )

    def evaluate(self, trade: ProposedTrade) -> Tuple[bool, List[GateResult]]:
        """
        Run all gates. Returns (all_passed, list_of_results).
        """
        results = [
            self.gate_leverage(trade),
            self.gate_concentration(trade),
            self.gate_oi_share(trade),
            self.gate_gap_stress(trade),
            self.gate_impact_vs_edge(trade),
            self.gate_correlation(trade),
        ]
        all_ok = all(r.allowed for r in results)
        return all_ok, results

    def explain(self, results: List[GateResult]) -> str:
        lines = []
        for r in results:
            status = "PASS" if r.allowed else "FAIL"
            lines.append(f"[{status}] {r.gate_name}: {r.reason}")
        return "\n".join(lines)
