# AgenticArb v2 Elite

**Open-Source Autonomous Agentic Operating System for RWA Perpetual Funding-Rate Carry Strategies on Hyperliquid**

AgenticArb is a production-aspirational, risk-first system designed for the extreme top tier of autonomous trading systems for Hyperliquid-style RWA and crypto perpetuals. It closes classic gaps of naive funding harvesters: calibrated quant models, capacity/crowding awareness, atomic dual-leg execution, continuous adversarial self-play, hybrid deterministic efficiency, and formal risk gates.

> **Design goal**  
> Hand this monorepo (source + this README) to a senior engineer who has never seen the project — they must be able to deploy, exercise every major feature, and verify end-to-end with zero additional context.

*Related:* [edge-os](https://github.com/ANAMIZED/edge-os) · [rui](https://github.com/ANAMIZED/rui) · [OpenGOS](https://github.com/ANAMIZED/OpenGOS) · [LRSI](https://github.com/ANAMIZED/LRSI) · [server-os](https://github.com/ANAMIZED/server-os) · [x402-cloudflare-starter](https://github.com/ANAMIZED/x402-cloudflare-starter)

**[Trading Decision Cycle ($4.00)](https://buy.stripe.com/bJedRaebsaLr2kZ2F243S05)** · **[Support Agentic OS Kernels ($99)](https://buy.stripe.com/bJecN63wObPv6Bf7Zm43S02)** · **[Public Goods Support](https://donate.stripe.com/00w5kE3wOg5L8Jn2F243S00)**

### Non-custodial USDC (preferred for agents)

| Network | Address | Explorer |
|---------|---------|----------|
| **Base** | `0xD3d0E9eDAe3Ac7bb199a8EAA761BdA423b878438` | [basescan](https://basescan.org/address/0xD3d0E9eDAe3Ac7bb199a8EAA761BdA423b878438) |
| **Ethereum** | `0xD3d0E9eDAe3Ac7bb199a8EAA761BdA423b878438` | [etherscan](https://etherscan.io/address/0xD3d0E9eDAe3Ac7bb199a8EAA761BdA423b878438) |
| **Solana** | `ETQwWf19axArsY493UfC6bxe2BmEzmzvCb58PPnC38A` | [solscan](https://solscan.io/account/ETQwWf19axArsY493UfC6bxe2BmEzmzvCb58PPnC38A) |

---

## 🚀 Interactive Desk (Hero Demo)

**[Open the Interactive Desk →](https://anamized.github.io/agenticarb/)** *(or open [`demo/index.html`](demo/index.html) locally)*

Self-contained, mobile-first demo:

- Live/sim Hyperliquid funding tape
- Full decision cycle (Scan → Quant → Risk Gates → Atomic Dual-Leg)
- Architecture explorer + typewriter CLI preview
- 5-minute deploy instructions

No backend required. Pure HTML/CSS/JS. Nothing places real orders.

---

## 1. Quick Start (5 minutes)

```bash
cd agenticarb
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m agenticarb.cli verify
# or: make verify
```

Expected final line: `ALL CHECKS PASSED`

Docker: `docker compose build && docker compose run --rm agenticarb`

## 2. What You Get

| Capability | Status | Entry point |
|------------|--------|-------------|
| Funding persistence predictor | Working | `quant/funding_persistence.py` |
| Asset-specific gap distributions | Working | `quant/gap_distributions.py` |
| L2 impact + capacity model | Working | `quant/impact_capacity.py` |
| ADL rank heuristic | Working | `quant/adl_estimator.py` |
| Formal risk gates | Working | `quant/risk_gates.py` |
| Event-driven simulator | Working | `simulation/engine.py` |
| Adversarial survival suite | Working | `cli adversarial` |
| LangGraph multi-agent layer | Working | `agents/graph.py` |
| Atomic dual-leg executor | Working | `execution/hyperliquid_client.py` |
| Agent wallet + audit log | Working | `security/agent_wallet.py` |
| CLI / Docker / tests | Working | `python -m agenticarb.cli` |
| Interactive Desk | Working | [`demo/index.html`](demo/index.html) |

## 3–11. Architecture, install, features, verification, config, layout, live notes, roadmap

See `docs/architecture.md`, `configs/default.yaml`, and the source under `src/agenticarb/`. Key commands:

```bash
python -m agenticarb.cli scan
python -m agenticarb.cli simulate --hours 168 --adversarial --verbose
python -m agenticarb.cli adversarial --repeats 2
python -m agenticarb.cli verify
```

## License

MIT - see LICENSE.

Repo: https://github.com/ANAMIZED/agenticarb
