"""
RISK AGENT — A2A Server (JSON-RPC 2.0)
---------------------------------------
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
    "name": "Risk Assessment Agent",
    "description": "Identifies regulatory, cultural, and operational M&A risks using MCP tools",
    "url": "http://localhost:8002",
    "version": "1.0.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "skills": [
        {
            "id": "risk_assessment",
            "name": "M&A Risk Assessment",
            "description": "Runs MCP regulatory tools and synthesizes risk profile with Claude",
            "inputModes": ["data"],
            "outputModes": ["text", "data"],
        }
    ],
}


async def run_mcp_risk(company: str, profile: dict) -> tuple[dict, str]:
    """Call MCP regulatory tool via SDK stdio transport, then interpret with Claude."""
    server_params = StdioServerParameters(command=sys.executable, args=[MCP_SERVER_PATH])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            reg = await session.call_tool(
                "flag_regulatory_risk",
                {
                    "industry": profile.get("industry", "Technology"),
                    "deal_size_usd_millions": float(profile.get("deal_size_usd_millions", 100)),
                },
            )

    reg_data = json.loads(reg.content[0].text)

    prompt = f"""You are a Risk Assessment Agent in an M&A assessment system.

MCP Regulatory Tool Result:
{json.dumps(reg_data)}

Company Profile:
- Name: {company}
- Industry: {profile.get("industry")}
- Employees: {profile.get("employees")}
- Geography: {profile.get("geography", "US")}
- Notes: {profile.get("notes", "None")}

Write a concise risk assessment (bullet points):
- Regulatory risks (from MCP tool)
- Cultural / integration risks
- Operational risks
- Top 3 red flags (if any)
- Overall risk level: Low / Medium / High"""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    return {"regulatory": reg_data}, resp.content[0].text


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
    profile = payload.get("profile", {})

    mcp_results, analysis = await run_mcp_risk(company, profile)

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
    uvicorn.run(app, host="0.0.0.0", port=8002)
