"""Non-Custodial Agent Wallet Helpers - session keys with spend limits, asset restrictions, time bounds, decision logging."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import hashlib, json, time

@dataclass
class SessionKeyPolicy:
    max_notional_per_order: float
    max_notional_per_day: float
    allowed_assets: List[str]
    expires_at: float
    can_withdraw: bool = False
    can_transfer: bool = False

@dataclass
class DecisionLogEntry:
    ts: float
    cycle_id: str
    action: str
    payload_hash: str
    gates_passed: bool
    signature: Optional[str] = None

class AgentWalletGuard:
    def __init__(self, policy: SessionKeyPolicy):
        self.policy = policy
        self.daily_notional = 0.0
        self.day_start = time.time()
        self.logs: List[DecisionLogEntry] = []

    def _roll_day(self) -> None:
        if time.time() - self.day_start > 86400:
            self.daily_notional = 0.0
            self.day_start = time.time()

    def check_order(self, asset: str, notional: float) -> tuple[bool, str]:
        self._roll_day()
        if time.time() > self.policy.expires_at:
            return False, "session_key_expired"
        if asset.upper() not in [a.upper() for a in self.policy.allowed_assets]:
            return False, f"asset_not_allowed:{asset}"
        if notional > self.policy.max_notional_per_order:
            return False, "exceeds_per_order_limit"
        if self.daily_notional + notional > self.policy.max_notional_per_day:
            return False, "exceeds_daily_limit"
        if self.policy.can_withdraw:
            return False, "withdraw_rights_forbidden_for_agent"
        return True, "ok"

    def record_decision(self, cycle_id: str, action: str, payload: Dict, gates_passed: bool) -> DecisionLogEntry:
        blob = json.dumps(payload, sort_keys=True, default=str)
        h = hashlib.sha256(blob.encode()).hexdigest()
        entry = DecisionLogEntry(time.time(), cycle_id, action, h, gates_passed)
        self.logs.append(entry)
        if gates_passed and action.startswith("order"):
            self.daily_notional += float(payload.get("notional", 0))
        return entry

    def export_audit_trail(self) -> List[Dict]:
        return [e.__dict__ for e in self.logs]

def make_default_policy(assets: Optional[List[str]] = None, hours_valid: float = 24.0, max_order: float = 50_000.0, max_day: float = 250_000.0) -> SessionKeyPolicy:
    return SessionKeyPolicy(max_order, max_day, assets or ["BTC", "ETH", "TSLA", "GOLD", "NVDA", "CL"], time.time() + hours_valid * 3600, False, False)
