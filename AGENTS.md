# AGENTS.md — AgenticArb

Contract for AI coding agents working on this repository.

## What this project is

AgenticArb is an open-source Autonomous Agentic Operating System for **RWA perpetual funding-rate carry strategies on Hyperliquid**. It is risk-first: calibrated quant models, capacity/crowding awareness, atomic dual-leg execution, adversarial self-play, and formal risk gates.

A senior engineer with only the source and `README.md` must be able to deploy, exercise every major feature, and verify end-to-end with zero tribal knowledge.

## How to run & verify

```bash
pip install -e ".[dev]"
python -m agenticarb.cli verify
# or
make verify
```

Must print `ALL CHECKS PASSED`.

## Hard rules for agents

1. Never break the verify contract.
2. Fail closed — risk gates are pure functions; do not soften them.
3. Prefer offline/sim paths; never place real orders unless `MODE=live` is explicit.
4. Agent wallets must never have withdrawal rights.
5. Prefer small, focused changes. Update README.md and AGENTS.md when public surfaces change.
6. Keep the critical path deterministic; LLM only on anomaly / meta-review paths.

## Surfaces that must stay working

| Surface | Entry |
|---------|-------|
| CLI | `python -m agenticarb.cli scan|simulate|adversarial|verify` |
| Quant / risk | `src/agenticarb/quant/` |
| Execution | dual-leg + Hyperliquid client |
| Simulation | high-fidelity engine + adversarial suite |
| Security | non-custodial session-key agent wallet |
| Interactive Desk | `demo/index.html` |
| Tests | `pytest` / `make test` |

## Related

- [OpenGOS](https://github.com/ANAMIZED/OpenGOS) · [LRSI](https://github.com/ANAMIZED/LRSI) · [server-os](https://github.com/ANAMIZED/server-os) · [edge-os](https://github.com/ANAMIZED/edge-os) · [x402-cloudflare-starter](https://github.com/ANAMIZED/x402-cloudflare-starter)
