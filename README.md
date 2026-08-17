# AgenticArb v2 Elite

**Open-Source Autonomous Agentic Operating System for RWA Perpetual Funding-Rate Carry Strategies on Hyperliquid**

AgenticArb is a production-aspirational, risk-first system designed for the extreme top tier of autonomous trading systems for Hyperliquid-style RWA and crypto perpetuals. It closes classic gaps of naive funding harvesters: calibrated quant models, capacity/crowding awareness, atomic dual-leg execution, continuous adversarial self-play, hybrid deterministic efficiency, and formal risk gates.

> **Design goal**  
> Hand this monorepo (source + this README) to a senior engineer who has never seen the project — they must be able to deploy, exercise every major feature, and verify end-to-end with zero additional context.

*Related:* [OpenGOS](https://github.com/ANAMIZED/OpenGOS) (grants MCP) · [LRSI](https://github.com/ANAMIZED/LRSI) / [server-os](https://github.com/ANAMIZED/server-os) (agentic OS kernels) · [x402-cloudflare-starter](https://github.com/ANAMIZED/x402-cloudflare-starter)

**[Support Public Goods](https://donate.stripe.com/00w5kE3wOg5L8Jn2F243S00)** · **[Support Agentic OS Kernels ($99)](https://buy.stripe.com/bJecN63wObPv6Bf7Zm43S02)**

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

## Table of Contents

1. [Quick Start (5 minutes)](#1-quick-start-5-minutes)
2. [What You Get](#2-what-you-get)
3. [Architecture](#3-architecture)
4. [Installation](#4-installation)
5. [Using Every Feature](#5-using-every-feature)
6. [End-to-End Verification](#6-end-to-end-verification)
7. [Configuration](#7-configuration)
8. [Project Layout](#8-project-layout)
9. [Live Trading Notes](#9-live-trading-notes)
10. [Roadmap & Differentiation](#10-roadmap--differentiation)
11. [License](#11-license)

---

## 1. Quick Start (5 minutes)

```bash
# Clone / unpack the repository
cd agenticarb

# Create a virtualenv (recommended)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install
pip install -e ".[dev]"

# Full system verification (must exit 0)
python -m agenticarb.cli verify

# Or via Make
make verify
```

Expected final line:

```
ALL CHECKS PASSED
A senior engineer can now deploy, use every feature, and verify E2E.
```

Docker alternative (no local Python deps):

```bash
docker compose build
docker compose run --rm agenticarb
```

---

## 2. What You Get

| Capability | Status in this repo | Entry point |
|------------|---------------------|-------------|
| Funding persistence predictor (regime-aware) | Working | `quant/funding_persistence.py` |
| Asset-specific empirical gap distributions | Working | `quant/gap_distributions.py` |
| L2 impact + dynamic capacity model | Working | `quant/impact_capacity.py` |
| ADL rank heuristic | Working | `quant/adl_estimator.py` |
| Formal risk gates (pure functions) | Working | `quant/risk_gates.py` |
| High-fidelity event-driven simulator | Working | `simulation/engine.py` |
| Adversarial episode injection & survival suite | Working | `cli adversarial` |
| LangGraph multi-agent cognitive layer | Working (hybrid) | `agents/graph.py` |
| Atomic dual-leg executor (mock + live interface) | Working | `execution/hyperliquid_client.py` |
| Non-custodial session-key agent wallet + audit log | Working | `security/agent_wallet.py` |
| CLI for scan / simulate / adversarial / verify | Working | `python -m agenticarb.cli` |
| Docker Compose one-command verification | Working | `docker compose run` |
| Unit + E2E tests | Working | `pytest` / `make test` |
| Interactive Desk demo | Working | [`demo/index.html`](demo/index.html) |

The critical path is fully deterministic. LLM calls are gated behind anomaly scores and meta-review schedules (hybrid architecture).

---

## 3. Architecture

See docs/architecture.md and the original blueprint. Hybrid design: deterministic quant/risk for >=95% of cycles; LangGraph agents only on anomalies or meta-evolution.

---

## 4. Installation

### Prerequisites

- Python 3.10+
- (Optional) Docker & Docker Compose
- (Optional, live only) Hyperliquid account + private key for agent wallet

### From source

```bash
git clone https://github.com/ANAMIZED/agenticarb.git && cd agenticarb
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify the install

```bash
python -m agenticarb.cli verify
# or
make verify
# or
pytest tests/ -v
```

---

## 5. Using Every Feature

### 5.1 One-shot opportunity scan + risk-approved trades

```bash
python -m agenticarb.cli scan
```

### 5.2 High-fidelity simulation (paper twin)

```bash
python -m agenticarb.cli simulate --hours 168 --adversarial --verbose
```

### 5.3 Continuous adversarial self-play / red-team suite

```bash
python -m agenticarb.cli adversarial --repeats 2
```

### 5.4 Programmatic quant / risk / dual-leg / wallet

See source under `src/agenticarb/quant/`, `execution/`, `security/` and the examples in the original detailed README sections.

### 5.5 Full LangGraph cycle

```python
from agenticarb.agents.graph import run_cycle
result = run_cycle({"TSLA": {"funding": 0.00025, "premium": 0.0018, "oi_imbalance": 0.3, "vol": 0.035, "tradfi_session": True, "compression": 0.1}}, equity=100000)
print(result["final_decision"])
```

---

## 6. End-to-End Verification

```bash
python -m agenticarb.cli verify
```

Must print `ALL CHECKS PASSED`.

Additional: `make test`, `make adversarial`, `make docker-verify`.

---

## 7. Configuration

`configs/default.yaml` controls risk limits, quant thresholds, execution SLA, security session keys, and agent anomaly thresholds.

---

## 8. Project Layout

```
agenticarb/
├── README.md
├── LICENSE (MIT)
├── pyproject.toml / requirements.txt / Dockerfile / docker-compose.yml / Makefile
├── configs/default.yaml
├── demo/index.html          # Interactive Desk (display highlight)
├── src/agenticarb/
│   ├── cli.py
│   ├── quant/          # persistence, gaps, impact/capacity, ADL, risk gates
│   ├── agents/graph.py # LangGraph multi-agent
│   ├── execution/      # dual-leg + HL client
│   ├── simulation/     # high-fid engine + adversarial
│   └── security/       # agent wallet + audit
├── tests/unit + e2e
├── scripts/verify_system.py
├── docs/architecture.md
└── rust/README.md      # future critical path
```

---

## 9. Live Trading Notes

Safe-by-default paper/sim path. Live requires hyperliquid-python-sdk, agent wallet (no withdrawal rights), session keys enforced by AgentWalletGuard, and explicit MODE=live. Never grant withdrawal rights to agent wallets.

---

## 10. Roadmap & Differentiation

Phase 1-4 as in blueprint. AgenticArb is a complete capacity-aware, adversarially hardened hybrid OS for RWA perpetuals microstructure, not a simple funding bot.

---

## 11. License

MIT - see LICENSE.

Repo: https://github.com/ANAMIZED/agenticarb
