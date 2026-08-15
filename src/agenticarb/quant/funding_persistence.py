"""
Funding Persistence Predictor
=============================
Regime-switching / online Bayesian updater for expected remaining duration
of elevated funding rates on Hyperliquid (and similar) RWA/crypto perps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np
from collections import deque


class FundingRegime(str, Enum):
    HIGH_POSITIVE = "high_positive"
    HIGH_NEGATIVE = "high_negative"
    NEUTRAL = "neutral"
    COMPRESSED = "compressed"


@dataclass
class FundingFeatures:
    funding_rate: float
    premium: float
    oi_imbalance: float
    realized_vol_1h: float
    is_tradfi_session: bool
    recent_compression: float
    timestamp: float = 0.0


@dataclass
class PersistencePrediction:
    expected_remaining_hours: float
    p_flip_next_4h: float
    p_flip_next_12h: float
    regime: FundingRegime
    confidence: float
    edge_score: float
    diagnostics: Dict = field(default_factory=dict)


class FundingPersistencePredictor:
    def __init__(self, half_life_hours: float = 6.0, high_threshold: float = 0.00015, low_threshold: float = -0.00015, history_len: int = 168):
        self.half_life = half_life_hours
        self.high_th = high_threshold
        self.low_th = low_threshold
        self.history: deque = deque(maxlen=history_len)
        self._alpha = 1.0 - np.exp(-np.log(2) / half_life_hours)
        self._regime_counts: Dict[FundingRegime, int] = {r: 0 for r in FundingRegime}
        self._last_regime: Optional[FundingRegime] = None

    def update(self, features: FundingFeatures) -> None:
        self.history.append(features)
        regime = self._classify(features)
        self._regime_counts[regime] += 1
        self._last_regime = regime

    def _classify(self, f: FundingFeatures) -> FundingRegime:
        rate = f.funding_rate
        if abs(rate) < 0.00005 and f.recent_compression > 0.6:
            return FundingRegime.COMPRESSED
        if rate >= self.high_th:
            return FundingRegime.HIGH_POSITIVE
        if rate <= self.low_th:
            return FundingRegime.HIGH_NEGATIVE
        return FundingRegime.NEUTRAL

    def predict(self, features: Optional[FundingFeatures] = None) -> PersistencePrediction:
        if features is not None:
            self.update(features)
        if len(self.history) < 3:
            return PersistencePrediction(2.0, 0.4, 0.6, FundingRegime.NEUTRAL, 0.2, 0.0, {"reason": "insufficient_history"})
        current = self.history[-1]
        regime = self._classify(current)
        same_regime_streak = 0
        for f in reversed(self.history):
            if self._classify(f) == regime:
                same_regime_streak += 1
            else:
                break
        base_duration = self.half_life * (1.0 + 0.3 * np.log1p(same_regime_streak))
        oi_factor = 1.0 + 0.4 * abs(current.oi_imbalance)
        session_factor = 0.75 if current.is_tradfi_session and abs(current.funding_rate) > 0.0001 else 1.0
        vol_factor = 1.0 / (1.0 + 2.0 * current.realized_vol_1h)
        expected_remaining = max(0.5, base_duration * oi_factor * session_factor * vol_factor)
        p_flip_4 = 1.0 / (1.0 + np.exp((expected_remaining - 4.0) / 2.5))
        p_flip_12 = 1.0 / (1.0 + np.exp((expected_remaining - 12.0) / 4.0))
        sign = np.sign(current.funding_rate)
        expected_capture = abs(current.funding_rate) * expected_remaining * (1.0 - 0.5 * p_flip_4)
        edge_score = expected_capture * (1.0 - current.realized_vol_1h) * (1.0 - abs(current.oi_imbalance) * 0.3)
        confidence = min(0.95, 0.4 + 0.1 * np.log1p(len(self.history)) + 0.05 * same_regime_streak)
        return PersistencePrediction(float(expected_remaining), float(np.clip(p_flip_4, 0.05, 0.95)), float(np.clip(p_flip_12, 0.1, 0.98)), regime, float(confidence), float(edge_score * sign), {"streak": same_regime_streak})

    def reset(self) -> None:
        self.history.clear()
        self._regime_counts = {r: 0 for r in FundingRegime}
        self._last_regime = None


def create_predictor_for_asset(asset: str) -> FundingPersistencePredictor:
    if asset.upper() in {"TSLA", "AAPL", "NVDA", "SPX", "GOLD", "XAU", "CL", "WTI", "EUR", "JPY"}:
        return FundingPersistencePredictor(half_life_hours=4.5, high_threshold=0.00012)
    return FundingPersistencePredictor()
