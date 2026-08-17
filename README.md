# AgenticArb v2 Elite

[![CI](https://github.com/ANAMIZED/agenticarb/actions/workflows/ci.yml/badge.svg)](https://github.com/ANAMIZED/agenticarb/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-server-purple.svg)](src/agenticarb/mcp/)
[![SDK](https://img.shields.io/badge/SDK-Python-green.svg)](src/agenticarb/sdk/)
[![CLI](https://img.shields.io/badge/CLI-agenticarb-orange.svg)](src/agenticarb/cli.py)
[![API](https://img.shields.io/badge/API-FastAPI-009688.svg)](src/agenticarb/api/)

**Open-Source Autonomous Agentic Operating System for RWA Perpetual Funding-Rate Carry Strategies on Hyperliquid**

*Related:* [edge-os](https://github.com/ANAMIZED/edge-os) · [rui](https://github.com/ANAMIZED/rui) · [OpenGOS](https://github.com/ANAMIZED/OpenGOS) · [LRSI](https://github.com/ANAMIZED/LRSI) · [server-os](https://github.com/ANAMIZED/server-os)

**[Trading Decision Cycle ($4.00)](https://buy.stripe.com/bJedRaebsaLr2kZ2F243S05)** · **[Support Agentic OS Kernels ($99)](https://buy.stripe.com/bJecN63wObPv6Bf7Zm43S02)** · **[Public Goods Support](https://donate.stripe.com/00w5kE3wOg5L8Jn2F243S00)**

## Surfaces

| Surface | Entry |
|---------|-------|
| **CLI** | `agenticarb` / `python -m agenticarb.cli` |
| **SDK** | `from agenticarb.sdk import AgenticArbClient` |
| **REST API** | `agenticarb-api` → http://localhost:8080/docs |
| **MCP Server** | `agenticarb-mcp` |
| **Multi-agent** | `agenticarb.agents.graph.run_cycle` + `skills/multi-agent-workflow/` |
| **CI** | `.github/workflows/ci.yml` |
| **Interactive Desk** | [`demo/index.html`](demo/index.html) |

## Quick Start

```bash
pip install -e ".[dev,api,mcp]"
python -m agenticarb.cli verify
agenticarb-api
```

## License

MIT — see LICENSE.
