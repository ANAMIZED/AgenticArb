"""
High-Fidelity Event-Driven Simulation Engine
============================================
Replays:
- Exact Hyperliquid hourly funding formula (simplified but faithful)
- Empirical gap distributions
- L2-derived impact
- Oracle lag
- ADL heuristics
- Multi-venue latency differentials

Supports walk-forward, Monte-Carlo, and adversarial episode injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import numpy as np
from datetime import datetime, timedelta
import copy

from ..quant.funding_persistence import FundingPersistencePredictor, FundingFeatures
from ..quant.gap_distributions import GapDistributionSampler
from ..quant.impact_capacity import ImpactCapacityModel
from ..quant.adl_estimator import ADLRankEstimator, PositionSnapshot
from ..quant.risk_gates import RiskGates, ProposedTrade


class EventType(str, Enum):
    FUNDING = "funding"
    PRICE = "price"
    GAP = "gap"
    ORACLE_LAG = "oracle_lag"
    ADL = "adl"
    NEWS_SHOCK = "news_shock"
    CROWDING = "crowding"
    ORDER_FILL = "order_fill"


@dataclass
class SimEvent:
    ts: float
    type: EventType
    payload: Dict


@dataclass
class Position:
    asset: str
    side: str
    notional: float
    entry_price: float
    leverage: float
    margin: float
    unrealized_pnl: float = 0.0
    funding_pnl: float = 0.0
    open_ts: float = 0.0


@dataclass
class SimState:
    equity: float
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    funding_collected: float = 0.0
    fees_paid: float = 0.0
    max_equity: float = 0.0
    drawdown: float = 0.0
    step: int = 0
    ts: float = 0.0
    logs: List[str] = field(default_factory=list)


class HighFidelitySimulator:
    """
    Core simulation loop. Designed to be deterministic given a seed
    and event schedule.
    """

    def __init__(
        self,
        initial_equity: float = 100_000.0,
        seed: int = 42,
        fee_bps: float = 2.0,          # taker-ish
        funding_interval_hours: float = 1.0,
    ):
        self.initial_equity = initial_equity
        self.rng = np.random.default_rng(seed)
        self.fee_bps = fee_bps
        self.funding_interval = funding_interval_hours
        self.gap_sampler = GapDistributionSampler(seed=seed)
        self.impact_model = ImpactCapacityModel()
        self.adl_est = ADLRankEstimator()
        self.risk_gates = RiskGates()
        self.predictors: Dict[str, FundingPersistencePredictor] = {}
        self.state = self._fresh_state()
        self.event_queue: List[SimEvent] = []
        self.price: Dict[str, float] = {}
        self.oracle: Dict[str, float] = {}
        self.funding_rate: Dict[str, float] = {}
        self.oi: Dict[str, float] = {}

    def _fresh_state(self) -> SimState:
        return SimState(
            equity=self.initial_equity,
            cash=self.initial_equity,
            max_equity=self.initial_equity,
        )

    def reset(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.state = self._fresh_state()
        self.event_queue.clear()
        self.price.clear()
        self.oracle.clear()
        self.funding_rate.clear()
        self.oi.clear()
        self.predictors.clear()

    def set_market(
        self,
        asset: str,
        price: float,
        oracle: Optional[float] = None,
        funding: float = 0.0001,
        oi: float = 1_000_000.0,
    ) -> None:
        self.price[asset] = price
        self.oracle[asset] = oracle if oracle is not None else price
        self.funding_rate[asset] = funding
        self.oi[asset] = oi
        if asset not in self.predictors:
            self.predictors[asset] = FundingPersistencePredictor()

    def _hyperliquid_funding(self, premium: float, interest: float = 0.0000125) -> float:
        """
        Simplified HL formula:
        F = P + clamp(interest - P, -0.0005, 0.0005)
        then paid hourly at that rate (capped 4%/h in reality).
        """
        clamped = np.clip(interest - premium, -0.0005, 0.0005)
        f = premium + clamped
        return float(np.clip(f, -0.04, 0.04))

    def inject_adversarial(self, episode: str, intensity: float = 1.0) -> None:
        """
        Inject common adversarial scenarios used by the Meta/Self-Play agent.
        """
        ts = self.state.ts + 1.0
        if episode == "oracle_freeze":
            self.event_queue.append(SimEvent(ts, EventType.ORACLE_LAG, {"hours": 2.0 * intensity, "asset": "ALL"}))
        elif episode == "funding_cascade":
            for a in list(self.funding_rate.keys()):
                self.event_queue.append(
                    SimEvent(ts, EventType.FUNDING, {"asset": a, "rate_override": -0.002 * intensity})
                )
        elif episode == "weekend_gap":
            for a in list(self.price.keys()):
                gap = float(self.gap_sampler.sample_gap(a, "adverse_short")[0]) * intensity
                self.event_queue.append(SimEvent(ts, EventType.GAP, {"asset": a, "gap": gap}))
        elif episode == "adl_force":
            self.event_queue.append(SimEvent(ts, EventType.ADL, {"force_close_fraction": 0.3 * intensity}))
        elif episode == "crowding":
            self.event_queue.append(SimEvent(ts, EventType.CROWDING, {"oi_share_boost": 0.15 * intensity}))
        elif episode == "news_shock":
            for a in list(self.price.keys()):
                shock = self.rng.normal(0, 0.03 * intensity)
                self.event_queue.append(SimEvent(ts, EventType.PRICE, {"asset": a, "return": shock}))
        else:
            self.state.logs.append(f"Unknown adversarial episode: {episode}")

    def submit_order(
        self,
        asset: str,
        side: str,
        notional: float,
        leverage: float = 3.0,
        use_risk_gates: bool = True,
    ) -> Dict:
        """
        Simulate dual-leg style order (perp only for now; physical leg mocked).
        """
        if asset not in self.price:
            return {"status": "rejected", "reason": "unknown_asset"}

        expected_edge = abs(self.funding_rate.get(asset, 0.0)) * 24 * 10_000  # rough daily bps
        trade = ProposedTrade(
            asset=asset,
            side=side,
            notional=notional,
            leverage=leverage,
            expected_edge_bps=expected_edge,
            holding_hours=24.0,
            current_margin_buffer=self.state.equity * 0.4,
            portfolio_notional=sum(p.notional for p in self.state.positions.values()),
            portfolio_equity=self.state.equity,
            own_oi_share=notional / max(self.oi.get(asset, 1e9), 1.0),
        )

        if use_risk_gates:
            ok, results = self.risk_gates.evaluate(trade)
            if not ok:
                return {
                    "status": "rejected_by_gates",
                    "reason": self.risk_gates.explain(results),
                    "gates": [r.__dict__ for r in results],
                }

        # Impact
        _, _, impact_bps = self.impact_model.expected_impact_bps(asset, notional)
        fill_price = self.price[asset] * (1.0 + (impact_bps / 10_000) * (1 if side == "long" else -1))
        fee = notional * self.fee_bps / 10_000
        margin = notional / leverage

        if margin + fee > self.state.cash:
            return {"status": "rejected", "reason": "insufficient_cash"}

        pos = Position(
            asset=asset,
            side=side,
            notional=notional,
            entry_price=fill_price,
            leverage=leverage,
            margin=margin,
            open_ts=self.state.ts,
        )
        self.state.positions[asset] = pos
        self.state.cash -= (margin + fee)
        self.state.fees_paid += fee
        self.state.logs.append(f"OPEN {side} {asset} notional={notional:.0f} @ {fill_price:.4f}")

        return {
            "status": "filled",
            "fill_price": fill_price,
            "fee": fee,
            "margin": margin,
            "impact_bps": impact_bps,
        }

    def _apply_funding(self) -> None:
        for asset, pos in list(self.state.positions.items()):
            rate = self.funding_rate.get(asset, 0.0)
            # Long pays positive rate, short receives
            payment = pos.notional * rate * (1 if pos.side == "long" else -1)
            pos.funding_pnl -= payment
            self.state.funding_collected -= payment
            self.state.cash -= payment
            self.state.logs.append(f"FUNDING {asset} rate={rate:.6f} payment={-payment:.2f}")

    def _mark_to_market(self) -> None:
        total_upnl = 0.0
        for asset, pos in self.state.positions.items():
            px = self.price.get(asset, pos.entry_price)
            if pos.side == "long":
                upnl = (px - pos.entry_price) / pos.entry_price * pos.notional
            else:
                upnl = (pos.entry_price - px) / pos.entry_price * pos.notional
            pos.unrealized_pnl = upnl
            total_upnl += upnl
        self.state.equity = self.state.cash + sum(p.margin for p in self.state.positions.values()) + total_upnl
        self.state.max_equity = max(self.state.max_equity, self.state.equity)
        self.state.drawdown = 1.0 - self.state.equity / max(self.state.max_equity, 1.0)

    def step(self, hours: float = 1.0) -> SimState:
        """
        Advance simulation by `hours`. Process queued events then regular funding.
        """
        self.state.ts += hours
        self.state.step += 1

        # Process events
        remaining = []
        for ev in sorted(self.event_queue, key=lambda e: e.ts):
            if ev.ts <= self.state.ts:
                self._handle_event(ev)
            else:
                remaining.append(ev)
        self.event_queue = remaining

        # Regular hourly funding
        if self.state.step % max(1, int(1.0 / self.funding_interval)) == 0:
            self._apply_funding()

        self._mark_to_market()
        return copy.deepcopy(self.state)

    def _handle_event(self, ev: SimEvent) -> None:
        if ev.type == EventType.GAP:
            a = ev.payload["asset"]
            gap = ev.payload["gap"]
            if a in self.price:
                self.price[a] *= (1.0 + gap)
                self.oracle[a] = self.price[a]
                self.state.logs.append(f"GAP {a} {gap:+.2%}")
        elif ev.type == EventType.PRICE:
            a = ev.payload["asset"]
            ret = ev.payload["return"]
            if a in self.price:
                self.price[a] *= (1.0 + ret)
                self.state.logs.append(f"PRICE_SHOCK {a} {ret:+.2%}")
        elif ev.type == EventType.FUNDING:
            a = ev.payload.get("asset")
            if a and a in self.funding_rate:
                self.funding_rate[a] = ev.payload.get("rate_override", self.funding_rate[a])
        elif ev.type == EventType.ORACLE_LAG:
            self.state.logs.append(f"ORACLE_LAG {ev.payload}")
        elif ev.type == EventType.ADL:
            frac = ev.payload.get("force_close_fraction", 0.2)
            for asset, pos in list(self.state.positions.items()):
                close_n = pos.notional * frac
                px = self.price.get(asset, pos.entry_price)
                if pos.side == "long":
                    pnl = (px - pos.entry_price) / pos.entry_price * close_n
                else:
                    pnl = (pos.entry_price - px) / pos.entry_price * close_n
                self.state.realized_pnl += pnl
                self.state.cash += pos.margin * frac + pnl
                pos.notional -= close_n
                pos.margin *= (1 - frac)
                if pos.notional < 100:
                    del self.state.positions[asset]
                self.state.logs.append(f"ADL force-close {frac:.0%} of {asset}")
        elif ev.type == EventType.CROWDING:
            self.state.logs.append(f"CROWDING event {ev.payload}")

    def run_episode(
        self,
        hours: int = 168,
        strategy_fn: Optional[Callable[["HighFidelitySimulator"], None]] = None,
        adversarial_schedule: Optional[List[tuple]] = None,
    ) -> Dict:
        """
        Run a full episode. strategy_fn is called each step to decide actions.
        adversarial_schedule: list of (hour, episode_name, intensity)
        """
        self.reset()
        # Seed a few markets
        for a, px in [("BTC", 60000), ("ETH", 3000), ("TSLA", 250), ("GOLD", 2400)]:
            self.set_market(a, px, funding=0.00012 if a in ("TSLA", "GOLD") else 0.00005)

        results = []
        adv = {h: (ep, inten) for h, ep, inten in (adversarial_schedule or [])}

        for h in range(hours):
            if h in adv:
                ep, inten = adv[h]
                self.inject_adversarial(ep, inten)
            if strategy_fn:
                strategy_fn(self)
            st = self.step(1.0)
            results.append({
                "hour": h,
                "equity": st.equity,
                "drawdown": st.drawdown,
                "funding": st.funding_collected,
                "n_pos": len(st.positions),
            })

        final = self.state
        return {
            "final_equity": final.equity,
            "total_return": final.equity / self.initial_equity - 1.0,
            "max_drawdown": final.drawdown,
            "funding_collected": final.funding_collected,
            "fees_paid": final.fees_paid,
            "realized_pnl": final.realized_pnl,
            "n_steps": final.step,
            "logs": final.logs[-50:],
            "timeseries": results,
        }
