"""Unit tests for quant models."""
import pytest
from agenticarb.quant.funding_persistence import FundingPersistencePredictor, FundingFeatures, create_predictor_for_asset
from agenticarb.quant.gap_distributions import GapDistributionSampler
from agenticarb.quant.impact_capacity import ImpactCapacityModel
from agenticarb.quant.risk_gates import RiskGates, ProposedTrade
from agenticarb.quant.adl_estimator import ADLRankEstimator, PositionSnapshot

def test_funding_persistence_basic():
    pred = FundingPersistencePredictor()
    feats = FundingFeatures(0.00025, 0.002, 0.3, 0.02, True, 0.1)
    p = pred.predict(feats)
    assert p.expected_remaining_hours > 0
    assert 0 < p.p_flip_next_4h < 1
    assert p.confidence > 0

def test_asset_specific_predictor():
    p1 = create_predictor_for_asset("TSLA")
    p2 = create_predictor_for_asset("BTC")
    assert p1.half_life != p2.half_life or p1.high_th != p2.high_th

def test_gap_stats():
    gs = GapDistributionSampler(seed=1)
    stats = gs.get_stats("TSLA")
    assert stats.p99 > stats.p95 > 0
    stress = gs.stress_test_position("TSLA", "short", 50_000, 20_000, 3.0)
    assert "survives_95" in stress

def test_capacity_positive_edge():
    model = ImpactCapacityModel()
    cap = model.capacity_for_edge("TSLA", expected_net_edge_bps=40.0)
    assert cap.max_notional > 0

def test_capacity_zero_edge():
    model = ImpactCapacityModel()
    cap = model.capacity_for_edge("TSLA", expected_net_edge_bps=-5.0)
    assert cap.max_notional == 0.0

def test_risk_gates_pass():
    gates = RiskGates()
    trade = ProposedTrade("GOLD", "short", 15_000, 3.0, 25.0, 24, 50_000, 15_000, 100_000, own_oi_share=0.02)
    ok, results = gates.evaluate(trade)
    assert isinstance(ok, bool)
    assert len(results) == 6

def test_adl_estimator():
    est = ADLRankEstimator()
    pos = PositionSnapshot("TSLA", "short", 20_000, 4.0, 800, 250, 248, 100_000)
    r = est.estimate(pos)
    assert 0 < r.estimated_rank_percentile < 1
