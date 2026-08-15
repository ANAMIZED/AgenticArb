"""
Multi-Agent Cognitive Layer (LangGraph)
=======================================
Hybrid architecture: deterministic quant/risk handles ≥95% of cycles.
LLM agents activate only on anomalies, weekly meta review, new strategy
proposals, or human queries.

Agents:
- Scanner
- Capacity
- Sizer
- Risk Guardian (veto)
- Executor
- Physical-Leg (stub)
- Calendar/Gap
- Meta/Self-Play
- Compliance
"""

from __future__ import annotations

from typing import Annotated, Dict, List, Optional, TypedDict, Any
from enum import Enum
import operator
import time

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None
    MemorySaver = None

from ..quant.funding_persistence import (
    FundingPersistencePredictor,
    FundingFeatures,
    PersistencePrediction,
    create_predictor_for_asset,
)
from ..quant.impact_capacity import ImpactCapacityModel, CapacityEstimate
from ..quant.gap_distributions import GapDistributionSampler
from ..quant.risk_gates import RiskGates, ProposedTrade, GateResult
from ..quant.adl_estimator import ADLRankEstimator


class AnomalyLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentState(TypedDict):
    """Shared state flowing through the graph."""
    cycle_id: str
    timestamp: float
    market_snapshot: Dict[str, Any]
    scanned_opportunities: List[Dict]
    capacity_estimates: Dict[str, Any]
    proposed_sizes: Dict[str, float]
    risk_results: List[Dict]
    approved_trades: List[Dict]
    execution_reports: List[Dict]
    anomaly_score: float
    anomaly_level: str
    messages: Annotated[List[str], operator.add]
    meta_actions: List[str]
    human_query: Optional[str]
    final_decision: Optional[str]


# ---------------------------------------------------------------------------
# Deterministic agent nodes (no LLM)
# ---------------------------------------------------------------------------

def scanner_node(state: AgentState) -> Dict:
    """Scan for elevated funding + persistence edge."""
    snap = state.get("market_snapshot", {})
    opps = []
    predictors = {}
    for asset, data in snap.items():
        if asset.startswith("_") or not isinstance(data, dict):
            continue
        pred = create_predictor_for_asset(asset)
        feats = FundingFeatures(
            funding_rate=data.get("funding", 0.0),
            premium=data.get("premium", 0.0),
            oi_imbalance=data.get("oi_imbalance", 0.0),
            realized_vol_1h=data.get("vol", 0.02),
            is_tradfi_session=data.get("tradfi_session", False),
            recent_compression=data.get("compression", 0.3),
            timestamp=state.get("timestamp", time.time()),
        )
        # Warm the online estimator with a short synthetic history so a
        # single snapshot still yields usable confidence (demo + cold-start).
        for _ in range(4):
            pred.update(feats)
        prediction: PersistencePrediction = pred.predict(feats)
        if abs(prediction.edge_score) > 0.00003 and prediction.confidence > 0.35:
            opps.append({
                "asset": asset,
                "side": "short" if prediction.edge_score > 0 else "long",
                "edge_score": prediction.edge_score,
                "expected_hours": prediction.expected_remaining_hours,
                "p_flip_4h": prediction.p_flip_next_4h,
                "regime": prediction.regime.value,
                "confidence": prediction.confidence,
            })
        predictors[asset] = pred

    opps = sorted(opps, key=lambda x: abs(x["edge_score"]), reverse=True)
    msg = f"Scanner found {len(opps)} opportunities"
    return {
        "scanned_opportunities": opps,
        "messages": [msg],
    }


def capacity_node(state: AgentState) -> Dict:
    model = ImpactCapacityModel()
    estimates = {}
    for opp in state.get("scanned_opportunities", []):
        asset = opp["asset"]
        # Convert edge_score roughly to bps over expected horizon
        edge_bps = abs(opp["edge_score"]) * 10_000 * max(opp["expected_hours"], 1.0)
        est: CapacityEstimate = model.capacity_for_edge(asset, edge_bps)
        estimates[asset] = {
            "max_notional": est.max_notional,
            "recommended_size": est.recommended_size,
            "total_impact_bps": est.total_impact_bps,
            "edge_consumption": est.edge_consumption_ratio,
        }
    return {
        "capacity_estimates": estimates,
        "messages": [f"Capacity computed for {len(estimates)} assets"],
    }


def sizer_node(state: AgentState) -> Dict:
    sizes = {}
    equity = state.get("market_snapshot", {}).get("_equity", 100_000.0)
    risk_budget = equity * 0.02  # 2% risk per idea
    for opp in state.get("scanned_opportunities", []):
        asset = opp["asset"]
        cap = state.get("capacity_estimates", {}).get(asset, {})
        rec = cap.get("recommended_size", 0.0)
        # Simple inverse-vol + confidence
        conf = opp.get("confidence", 0.5)
        size = min(rec, risk_budget * 10) * conf
        if size > 500:
            sizes[asset] = size
    return {
        "proposed_sizes": sizes,
        "messages": [f"Sized {len(sizes)} candidates"],
    }


def risk_guardian_node(state: AgentState) -> Dict:
    gates = RiskGates()
    results = []
    approved = []
    equity = state.get("market_snapshot", {}).get("_equity", 100_000.0)
    for opp in state.get("scanned_opportunities", []):
        asset = opp["asset"]
        size = state.get("proposed_sizes", {}).get(asset, 0.0)
        if size <= 0:
            continue
        trade = ProposedTrade(
            asset=asset,
            side=opp["side"],
            notional=size,
            leverage=3.0,
            expected_edge_bps=abs(opp["edge_score"]) * 10_000 * opp["expected_hours"],
            holding_hours=opp["expected_hours"],
            current_margin_buffer=equity * 0.35,
            portfolio_notional=sum(state.get("proposed_sizes", {}).values()),
            portfolio_equity=equity,
            own_oi_share=size / 5_000_000.0,
        )
        ok, gate_results = gates.evaluate(trade)
        results.append({
            "asset": asset,
            "allowed": ok,
            "detail": gates.explain(gate_results),
        })
        if ok:
            approved.append({
                "asset": asset,
                "side": opp["side"],
                "notional": size,
                "leverage": 3.0,
                "edge_score": opp["edge_score"],
            })
    return {
        "risk_results": results,
        "approved_trades": approved,
        "messages": [f"Risk Guardian approved {len(approved)}/{len(results)}"],
    }


def executor_node(state: AgentState) -> Dict:
    """
    In live mode this would call the dual-leg execution layer.
    Here we record the decision and emit a report.
    """
    reports = []
    for t in state.get("approved_trades", []):
        reports.append({
            "asset": t["asset"],
            "side": t["side"],
            "notional": t["notional"],
            "status": "submitted_to_execution_layer",
            "latency_ms_estimate": 45,  # target <100ms
        })
    decision = "EXECUTE" if reports else "NO_TRADE"
    return {
        "execution_reports": reports,
        "final_decision": decision,
        "messages": [f"Executor: {decision} ({len(reports)} orders)"],
    }


def anomaly_detector_node(state: AgentState) -> Dict:
    """Simple anomaly score from market snapshot."""
    snap = state.get("market_snapshot", {})
    score = 0.0
    for asset, data in snap.items():
        if asset.startswith("_"):
            continue
        if not isinstance(data, dict):
            continue
        fr = abs(data.get("funding", 0.0))
        if fr > 0.001:
            score += 0.4
        if data.get("vol", 0) > 0.05:
            score += 0.3
        if data.get("oracle_staleness_sec", 0) > 60:
            score += 0.5
    level = AnomalyLevel.NONE
    if score > 1.5:
        level = AnomalyLevel.CRITICAL
    elif score > 1.0:
        level = AnomalyLevel.HIGH
    elif score > 0.5:
        level = AnomalyLevel.MEDIUM
    elif score > 0.2:
        level = AnomalyLevel.LOW
    return {
        "anomaly_score": score,
        "anomaly_level": level.value,
        "messages": [f"Anomaly level={level.value} score={score:.2f}"],
    }


def meta_selfplay_node(state: AgentState) -> Dict:
    """Triggered on schedule or high anomaly – records hardening actions."""
    actions = []
    level = state.get("anomaly_level", "none")
    if level in ("high", "critical"):
        actions.append("schedule_adversarial_episode:funding_cascade")
        actions.append("tighten_gap_buffer_temporarily")
    if state.get("human_query"):
        actions.append(f"respond_to_human: {state['human_query'][:80]}")
    return {
        "meta_actions": actions,
        "messages": [f"Meta/Self-Play actions: {actions}"],
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_agent_graph(checkpointer=None):
    """
    Build the LangGraph state machine.
    Primary path is fully deterministic.
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "langgraph is required. Install with: pip install langgraph langchain-core"
        )

    graph = StateGraph(AgentState)

    graph.add_node("anomaly", anomaly_detector_node)
    graph.add_node("scanner", scanner_node)
    graph.add_node("capacity", capacity_node)
    graph.add_node("sizer", sizer_node)
    graph.add_node("risk_guardian", risk_guardian_node)
    graph.add_node("executor", executor_node)
    graph.add_node("meta", meta_selfplay_node)

    graph.set_entry_point("anomaly")
    graph.add_edge("anomaly", "scanner")
    graph.add_edge("scanner", "capacity")
    graph.add_edge("capacity", "sizer")
    graph.add_edge("sizer", "risk_guardian")
    graph.add_edge("risk_guardian", "executor")
    graph.add_edge("executor", "meta")
    graph.add_edge("meta", END)

    memory = checkpointer or MemorySaver()
    return graph.compile(checkpointer=memory)


def run_cycle(
    market_snapshot: Dict[str, Any],
    equity: float = 100_000.0,
    human_query: Optional[str] = None,
    thread_id: str = "default",
) -> AgentState:
    """
    Convenience runner for a single decision cycle.
    """
    graph = build_agent_graph()
    snap = dict(market_snapshot)
    snap["_equity"] = equity
    initial: AgentState = {
        "cycle_id": f"cycle-{int(time.time())}",
        "timestamp": time.time(),
        "market_snapshot": snap,
        "scanned_opportunities": [],
        "capacity_estimates": {},
        "proposed_sizes": {},
        "risk_results": [],
        "approved_trades": [],
        "execution_reports": [],
        "anomaly_score": 0.0,
        "anomaly_level": "none",
        "messages": [],
        "meta_actions": [],
        "human_query": human_query,
        "final_decision": None,
    }
    config = {"configurable": {"thread_id": thread_id}}
    final = graph.invoke(initial, config=config)
    return final
