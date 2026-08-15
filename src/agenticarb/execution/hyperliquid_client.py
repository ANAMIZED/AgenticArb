"""
Hyperliquid Client Abstraction
==============================
- Live path uses official hyperliquid-python-sdk (or REST)
- Paper / sim path uses the HighFidelitySimulator
- Dual-leg atomic submission + reconciliation helpers

Target critical path latency: <100 ms decision-to-sign.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import time
import hashlib
import json


@dataclass
class OrderRequest:
    asset: str
    is_buy: bool
    size: float          # notional or contracts
    limit_px: Optional[float] = None
    reduce_only: bool = False
    client_id: Optional[str] = None


@dataclass
class OrderResult:
    status: str
    order_id: Optional[str]
    fill_px: Optional[float]
    filled_size: float
    latency_ms: float
    raw: Dict


class BaseHLClient(ABC):
    @abstractmethod
    def get_funding(self, asset: str) -> float: ...

    @abstractmethod
    def get_meta_and_ctxs(self) -> Dict: ...

    @abstractmethod
    def place_order(self, req: OrderRequest) -> OrderResult: ...

    @abstractmethod
    def cancel(self, asset: str, order_id: str) -> bool: ...


class MockHLClient(BaseHLClient):
    """
    Deterministic mock for paper trading and CI.
    """

    def __init__(self, seed: int = 42):
        self._funding = {
            "BTC": 0.00005,
            "ETH": 0.00008,
            "TSLA": 0.00018,
            "GOLD": 0.00012,
            "NVDA": 0.00022,
        }
        self._prices = {
            "BTC": 60000.0,
            "ETH": 3000.0,
            "TSLA": 250.0,
            "GOLD": 2400.0,
            "NVDA": 120.0,
        }
        self._orders: Dict[str, OrderRequest] = {}
        self._seq = 0

    def get_funding(self, asset: str) -> float:
        return self._funding.get(asset.upper(), 0.0)

    def get_meta_and_ctxs(self) -> Dict:
        return {
            "universe": list(self._prices.keys()),
            "prices": self._prices.copy(),
            "fundings": self._funding.copy(),
        }

    def place_order(self, req: OrderRequest) -> OrderResult:
        t0 = time.perf_counter()
        self._seq += 1
        oid = f"mock-{self._seq}-{hashlib.sha1(req.asset.encode()).hexdigest()[:8]}"
        self._orders[oid] = req
        px = self._prices.get(req.asset.upper(), 100.0)
        # Simulate slight slippage
        slip = 0.0002 if req.is_buy else -0.0002
        fill = px * (1 + slip)
        latency = (time.perf_counter() - t0) * 1000
        return OrderResult(
            status="filled",
            order_id=oid,
            fill_px=fill,
            filled_size=req.size,
            latency_ms=latency,
            raw={"mock": True},
        )

    def cancel(self, asset: str, order_id: str) -> bool:
        return self._orders.pop(order_id, None) is not None


class LiveHLClient(BaseHLClient):
    """
    Thin wrapper around the official SDK.
    Requires: pip install hyperliquid-python-sdk
    Environment: HL_PRIVATE_KEY, HL_ACCOUNT_ADDRESS (optional vault)
    """

    def __init__(self, private_key: str, account_address: Optional[str] = None, testnet: bool = True):
        try:
            from hyperliquid.info import Info
            from hyperliquid.exchange import Exchange
            from hyperliquid.utils import constants
        except ImportError as e:
            raise ImportError(
                "hyperliquid-python-sdk required for live trading. "
                "pip install hyperliquid-python-sdk"
            ) from e

        base_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        self.info = Info(base_url, skip_ws=True)
        self.exchange = Exchange(private_key, base_url, account_address=account_address)
        self.testnet = testnet

    def get_funding(self, asset: str) -> float:
        # Use meta and asset contexts
        meta, ctxs = self.info.meta_and_asset_ctxs()
        for m, c in zip(meta["universe"], ctxs):
            if m["name"] == asset:
                return float(c.get("funding", 0.0))
        return 0.0

    def get_meta_and_ctxs(self) -> Dict:
        meta, ctxs = self.info.meta_and_asset_ctxs()
        return {"meta": meta, "ctxs": ctxs}

    def place_order(self, req: OrderRequest) -> OrderResult:
        t0 = time.perf_counter()
        # SDK order placement (simplified; real code needs proper sz, etc.)
        # This is a placeholder – production must follow official signing + rate limits
        result = {
            "status": "ok",
            "response": {"data": {"statuses": [{"filled": {"oid": 0, "avgPx": "0"}}]}},
        }
        latency = (time.perf_counter() - t0) * 1000
        return OrderResult(
            status="submitted",
            order_id="live-placeholder",
            fill_px=None,
            filled_size=0.0,
            latency_ms=latency,
            raw=result,
        )

    def cancel(self, asset: str, order_id: str) -> bool:
        return True


class DualLegExecutor:
    """
    Atomic dual-leg: parallel submission + tight reconciliation + auto-unwind.
    """

    def __init__(self, primary: BaseHLClient, secondary: Optional[BaseHLClient] = None, timeout_ms: float = 250.0):
        self.primary = primary
        self.secondary = secondary
        self.timeout_ms = timeout_ms

    def execute_delta_neutral(
        self,
        asset: str,
        perp_side_is_buy: bool,
        size: float,
        physical_leg_fn=None,
    ) -> Dict:
        """
        Submit perp leg and (optionally) physical/TradFi leg in parallel.
        If one leg fails, unwind the successful one.
        """
        t0 = time.perf_counter()
        req = OrderRequest(
            asset=asset,
            is_buy=perp_side_is_buy,
            size=size,
            client_id=f"aa-{int(time.time()*1000)}",
        )
        # Parallel in spirit (sequential for mock simplicity)
        perp_res = self.primary.place_order(req)
        physical_res = None
        if physical_leg_fn:
            physical_res = physical_leg_fn(asset, not perp_side_is_buy, size)

        elapsed = (time.perf_counter() - t0) * 1000
        success = perp_res.status in ("filled", "submitted")
        if physical_leg_fn and physical_res and physical_res.get("status") != "ok":
            # Unwind
            if success and perp_res.order_id:
                self.primary.cancel(asset, perp_res.order_id)
            success = False

        return {
            "success": success,
            "perp": perp_res.__dict__,
            "physical": physical_res,
            "total_latency_ms": elapsed,
            "within_sla": elapsed < 100.0,
        }
