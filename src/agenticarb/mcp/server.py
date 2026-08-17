"""AgenticArb MCP server — scan, cycle, status tools."""
from __future__ import annotations

from typing import Any

try:
    from mcp.server import MCPServer

    mcp = MCPServer(
        "AgenticArb",
        instructions="AgenticArb funding-rate carry OS. Use tools for scan/cycle under risk gates.",
    )

    @mcp.tool()
    def agenticarb_status() -> dict[str, Any]:
        return {"service": "agenticarb", "version": "2.0.0", "mode": "offline"}

    @mcp.tool()
    def scan_opportunities() -> dict[str, Any]:
        return {"opportunities": [], "mode": "mock"}

    @mcp.tool()
    def run_decision_cycle(equity: float = 100000.0) -> dict[str, Any]:
        try:
            from agenticarb.agents.graph import run_cycle

            return run_cycle({}, equity=equity)
        except Exception as e:
            return {"error": str(e), "final_decision": "hold"}

    def main() -> None:
        mcp.run()

except ImportError:

    def main() -> None:
        raise SystemExit("Install mcp extra: pip install -e '.[mcp]'")


if __name__ == "__main__":
    main()
