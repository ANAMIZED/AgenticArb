# Architecture

See the top-level README for the full diagram and design rationale.

## Hybrid Deterministic + Agentic

```
Governance / Kill-Switch
        |
Multi-Agent Cognitive Layer (LangGraph – selective LLM)
  Scanner → Capacity → Sizer → Risk Guardian → Executor → Meta
        |
Deterministic Quant & Risk Core (Python now, Rust target)
  Persistence · Gaps · Impact/Capacity · ADL · Formal Gates
        |
Execution (Atomic Dual-Leg + Reconciliation)
        |
Data / Oracle / High-Fidelity Simulator
```

Critical path never calls an LLM. LLM is reserved for anomalies, weekly self-play review, and human MCP queries.
