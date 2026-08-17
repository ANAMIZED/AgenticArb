---
name: multi-agent-workflow
description: Run AgenticArb multi-agent decision cycle (Scan → Quant → Risk → Dual-Leg).
---

# Multi-agent workflow (AgenticArb)

## Entry points
- `from agenticarb.agents.graph import run_cycle`
- CLI: `python -m agenticarb.cli scan`
- API: `POST /v1/cycle`
- MCP: `run_decision_cycle`

Fail closed. Paper/sim by default.
