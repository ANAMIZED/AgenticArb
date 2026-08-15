"""End-to-end pipeline tests."""
import pytest
from agenticarb.simulation.engine import HighFidelitySimulator
from agenticarb.execution.hyperliquid_client import MockHLClient, DualLegExecutor
from agenticarb.security.agent_wallet import AgentWalletGuard, make_default_policy
from agenticarb.agents.graph import run_cycle, LANGGRAPH_AVAILABLE

def test_simulation_episode_completes():
    sim = HighFidelitySimulator(initial_equity=100_000, seed=123)
    result = sim.run_episode(hours=48)
    assert result["final_equity"] > 0

def test_dual_leg_mock_latency():
    client = MockHLClient()
    dual = DualLegExecutor(client)
    r = dual.execute_delta_neutral("GOLD", perp_side_is_buy=False, size=8_000)
    assert r["success"] is True

def test_agent_wallet_blocks_excess():
    policy = make_default_policy(max_order=5_000)
    guard = AgentWalletGuard(policy)
    ok, reason = guard.check_order("TSLA", 10_000)
    assert ok is False

@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_langgraph_cycle():
    market = {"TSLA": {"funding": 0.00025, "premium": 0.0018, "oi_imbalance": 0.28, "vol": 0.035, "tradfi_session": True, "compression": 0.15}}
    out = run_cycle(market, equity=150_000)
    assert out["final_decision"] in ("EXECUTE", "NO_TRADE")
