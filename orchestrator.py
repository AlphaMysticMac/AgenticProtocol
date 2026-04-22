"""
ORCHESTRATOR AGENT — A2A Server (JSON-RPC 2.0)
------------------------------------------------
  GET  /.well-known/agent.json  →  A2A agent card
  GET  /discover                →  fetch cards from all sub-agents
  POST /                        →  tasks/send handler

Delegates to sub-agents via A2A tasks/send (HTTP POST + JSON-RPC 2.0).
"""
import json, uuid
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
client = Anthropic()

FINANCIAL_AGENT_URL = "http://localhost:8001"
RISK_AGENT_URL = "http://localhost:8002"

AGENT_CARD = {
    "name": "MA Orchestrator Agent",
    "description": "Coordinates full M&A assessment by delegating to specialist agents via A2A",
    "url": "http://localhost:8000",
    "version": "1.0.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "skills": [
        {
            "id": "ma_assessment",
            "name": "Full M&A Assessment",
            "description": "Orchestrates financial + risk agents to produce a complete recommendation",
            "inputModes": ["data"],
            "outputModes": ["text", "data"],
        }
    ],
}


def _make_a2a_request(data: dict) -> dict:
    """Wrap a data payload in an A2A tasks/send JSON-RPC envelope."""
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tasks/send",
        "params": {
            "id": str(uuid.uuid4()),
            "message": {
                "role": "user",
                "parts": [{"type": "data", "data": data}],
            },
        },
    }


def _get_artifact(result: dict, name: str):
    """Extract a named artifact from an A2A task result."""
    for art in result.get("artifacts", []):
        if art["name"] == name:
            part = art["parts"][0]
            return part["text"] if part["type"] == "text" else part["data"]
    return None


@app.get("/.well-known/agent.json")
async def agent_card():
    return AGENT_CARD


@app.get("/discover")
async def discover():
    """A2A discovery: fetch agent cards from all sub-agents."""
    async with httpx.AsyncClient(timeout=5) as http:
        fin = (await http.get(f"{FINANCIAL_AGENT_URL}/.well-known/agent.json")).json()
        risk = (await http.get(f"{RISK_AGENT_URL}/.well-known/agent.json")).json()
    return {"orchestrator": AGENT_CARD, "sub_agents": [fin, risk]}


@app.post("/")
async def a2a_handler(request: Request):
    """A2A JSON-RPC 2.0 — dispatches tasks/send by delegating to sub-agents."""
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

    company = payload.get("company_name")
    financials = payload.get("financials", {})
    profile = payload.get("profile", {})

    async with httpx.AsyncClient(timeout=90) as http:
        # A2A call → Financial Agent
        fin_resp = await http.post(
            FINANCIAL_AGENT_URL,
            json=_make_a2a_request({"company_name": company, "financials": financials}),
        )
        fin_result = fin_resp.json()["result"]

        # A2A call → Risk Agent
        risk_resp = await http.post(
            RISK_AGENT_URL,
            json=_make_a2a_request({"company_name": company, "profile": profile}),
        )
        risk_result = risk_resp.json()["result"]

    fin_analysis = _get_artifact(fin_result, "analysis")
    fin_tools = _get_artifact(fin_result, "mcp_tool_results")
    risk_analysis = _get_artifact(risk_result, "analysis")
    risk_tools = _get_artifact(risk_result, "mcp_tool_results")

    synthesis_prompt = f"""You are the MA Orchestrator Agent.

Two specialist agents completed their analysis via the A2A protocol.

== FINANCIAL AGENT ==
{fin_analysis}

MCP Tool Results:
{json.dumps(fin_tools, indent=2)}

== RISK AGENT ==
{risk_analysis}

MCP Tool Results:
{json.dumps(risk_tools, indent=2)}

Synthesize a final M&A recommendation:
1. Executive Summary (2-3 sentences)
2. Recommendation: PROCEED / PROCEED WITH CONDITIONS / DO NOT PROCEED
3. Top 3 reasons
4. Suggested next steps"""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": synthesis_prompt}],
    )

    return {
        "jsonrpc": "2.0", "id": rpc_id,
        "result": {
            "id": task_id,
            "status": {"state": "completed"},
            "artifacts": [
                {
                    "name": "final_recommendation",
                    "parts": [{"type": "text", "text": resp.content[0].text}],
                },
                {
                    "name": "sub_agent_reports",
                    "parts": [{
                        "type": "data",
                        "data": {
                            "financial_analysis": fin_analysis,
                            "risk_assessment": risk_analysis,
                            "mcp_tool_results": {"financial": fin_tools, "risk": risk_tools},
                            "protocol_trace": {
                                "ui_to_orchestrator": "HTTP POST :8000  ·  A2A tasks/send (JSON-RPC 2.0)",
                                "orchestrator_to_financial": "HTTP POST :8001  ·  A2A tasks/send (JSON-RPC 2.0)",
                                "orchestrator_to_risk": "HTTP POST :8002  ·  A2A tasks/send (JSON-RPC 2.0)",
                                "agents_to_mcp": "stdio_client + ClientSession  ·  FastMCP subprocess (MCP SDK)",
                            },
                        },
                    }],
                },
            ],
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
