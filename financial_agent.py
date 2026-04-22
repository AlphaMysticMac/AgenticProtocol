"""
FINANCIAL AGENT — A2A Server (JSON-RPC 2.0)
--------------------------------------------
  GET  /.well-known/agent.json  →  A2A agent card
  POST /                        →  tasks/send handler
Internally calls MCP tools via the official mcp SDK (stdio_client + ClientSession).
"""
import json, sys, os, uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()
app = FastAPI()
client = Anthropic()

MCP_SERVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")

AGENT_CARD = {
    "name": "Financial Analysis Agent",
    "description": "Analyzes M&A financial health using MCP tools: valuation, debt ratio, revenue trends",
    "url": "http://localhost:8001",
    "version": "1.0.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "skills": [
        {
            "id": "financial_analysis",
            "name": "M&A Financial Analysis",
            "description": "Runs MCP tools for valuation and debt analysis, interprets with Claude",
            "inputModes": ["data"],
            "outputModes": ["text", "data"],
        }
    ],
}


async def run_mcp_analysis(company: str, financials: dict) -> tuple[dict, str]:
    """Call MCP tools via SDK stdio transport, then interpret results with Claude."""
    server_params = StdioServerParameters(command=sys.executable, args=[MCP_SERVER_PATH])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            valuation = await session.call_tool(
                "calculate_valuation",
                {
                    "ebitda": float(financials.get("ebitda", 10)),
                    "multiple": float(financials.get("industry_multiple", 8)),
                },
            )
            debt = await session.call_tool(
                "assess_debt_ratio",
                {
                    "net_debt": float(financials.get("net_debt", 20)),
                    "ebitda": float(financials.get("ebitda", 10)),
                },
            )

    val_data = json.loads(valuation.content[0].text)
    debt_data = json.loads(debt.content[0].text)

    prompt = f"""You are a Financial Analysis Agent in an M&A assessment system.

MCP Tool Results:
VALUATION: {json.dumps(val_data)}
DEBT RATIO: {json.dumps(debt_data)}

Company: {company}
Revenue: ${financials.get("revenue", "N/A")}M  |  EBITDA: ${financials.get("ebitda", "N/A")}M

Write a concise financial analysis (bullet points):
- Enterprise value assessment
- Debt health
- EBITDA margin quality
- Financial score: X/10
- Key concerns"""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    return {"valuation": val_data, "debt_ratio": debt_data}, resp.content[0].text


@app.get("/.well-known/agent.json")
async def agent_card():
    return AGENT_CARD


@app.post("/")
async def a2a_handler(request: Request):
    """A2A JSON-RPC 2.0 — dispatches tasks/send."""
    body = await request.json()
    rpc_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    if method != "tasks/send":
        return JSONResponse({
            "jsonrpc": "2.0", "id": rpc_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })

    task_id = params.get("id", str(uuid.uuid4()))
    parts = params.get("message", {}).get("parts", [])
    data_part = next((p for p in parts if p.get("type") == "data"), {})
    payload = data_part.get("data", {})

    company = payload.get("company_name", "Unknown")
    financials = payload.get("financials", {})

    mcp_results, analysis = await run_mcp_analysis(company, financials)

    return {
        "jsonrpc": "2.0", "id": rpc_id,
        "result": {
            "id": task_id,
            "status": {"state": "completed"},
            "artifacts": [
                {"name": "analysis", "parts": [{"type": "text", "text": analysis}]},
                {"name": "mcp_tool_results", "parts": [{"type": "data", "data": mcp_results}]},
            ],
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
