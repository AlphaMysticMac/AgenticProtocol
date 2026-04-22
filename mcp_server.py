"""
MCP SERVER — FastMCP SDK
-------------------------
Tools for M&A analysis exposed via the official MCP SDK.
Spawned as a subprocess by agents; communicates via stdio JSON-RPC.
Run directly to test: python mcp_server.py
"""
import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ma-tools-server")


@mcp.tool()
def calculate_valuation(ebitda: float, multiple: float) -> str:
    """Calculate enterprise value using EBITDA multiple."""
    ev = ebitda * multiple
    verdict = "Fair" if multiple <= 10 else "Premium" if multiple <= 15 else "Very high premium"
    return json.dumps({
        "enterprise_value_usd_millions": round(ev, 1),
        "multiple_used": multiple,
        "verdict": verdict,
        "note": f"EV of ${ev:.0f}M at {multiple}x EBITDA",
    })


@mcp.tool()
def assess_debt_ratio(net_debt: float, ebitda: float) -> str:
    """Assess leverage risk via Net Debt / EBITDA ratio."""
    ratio = net_debt / ebitda if ebitda != 0 else 999
    health = "Healthy (<3x)" if ratio < 3 else "Elevated (3-5x)" if ratio < 5 else "Concerning (>5x)"
    return json.dumps({
        "net_debt_to_ebitda": round(ratio, 2),
        "health": health,
        "refinancing_risk": "Low" if ratio < 3 else "Medium" if ratio < 5 else "High",
    })


@mcp.tool()
def flag_regulatory_risk(industry: str, deal_size_usd_millions: float) -> str:
    """Identify regulatory filing requirements and sector scrutiny."""
    flags = []
    high_scrutiny = {"defense", "telecom", "banking", "healthcare", "energy", "media"}
    if deal_size_usd_millions > 500:
        flags.append("HSR antitrust filing required (>$500M threshold)")
    if deal_size_usd_millions > 100:
        flags.append("Consider EU merger regulation notification")
    if industry.lower() in high_scrutiny:
        flags.append(f"{industry.title()} sector faces heightened regulatory review")
    return json.dumps({
        "flags": flags or ["No major regulatory flags"],
        "risk_level": "High" if len(flags) >= 2 else "Medium" if flags else "Low",
        "estimated_review_months": 6 if len(flags) >= 2 else 3 if flags else 1,
    })


if __name__ == "__main__":
    mcp.run()  # stdio transport — agents spawn this as a subprocess
