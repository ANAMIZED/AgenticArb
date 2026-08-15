# Rust Critical Path (Future)

The production design targets a Rust core (hypersdk or custom) for:

- Sub-100 ms orderbook aggregation
- Formal risk gates
- Dual-leg construction & signing

This directory is a placeholder. The current v2 Elite release implements the full
logic in high-performance Python so that a senior engineer can deploy, exercise
every feature, and verify end-to-end **today**.

Migration path:

1. Port `quant/risk_gates.py` and impact/capacity pure functions first.
2. Replace MockHLClient signing path with hypersdk.
3. Keep LangGraph cognitive layer in Python; call Rust via PyO3 or gRPC for the hot path.

See the main README for the hybrid architecture rationale.
