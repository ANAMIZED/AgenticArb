"""AgenticArb FastAPI application."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AgenticArb",
    description="Autonomous Agentic OS for RWA perpetual funding-rate carry strategies.",
    version="2.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "agenticarb", "version": "2.0.0"}


@app.get("/v1/status")
def status():
    return {
        "service": "agenticarb",
        "version": "2.0.0",
        "surfaces": ["cli", "sdk", "api", "mcp", "multi-agent"],
    }


@app.post("/v1/scan")
def scan():
    return {"opportunities": [], "mode": "mock"}


@app.post("/v1/cycle")
def cycle(payload: dict | None = None):
    try:
        from agenticarb.agents.graph import run_cycle

        data = payload or {}
        markets = data.get("markets", {})
        equity = data.get("equity", 100000)
        return run_cycle(markets, equity=equity)
    except Exception as e:
        return {"error": str(e), "mode": "mock", "final_decision": "hold"}


def run():
    import uvicorn

    uvicorn.run("agenticarb.api.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    run()
