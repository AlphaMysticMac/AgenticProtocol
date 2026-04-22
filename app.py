"""
STREAMLIT UI — A2A Client
--------------------------
Sends A2A tasks/send (JSON-RPC 2.0) to the Orchestrator.
Parses typed artifacts from the response.
"""
import streamlit as st
import httpx, json, uuid

ORCHESTRATOR_URL = "http://localhost:8000"

st.set_page_config(page_title="M&A Agent System", page_icon="🏦", layout="wide")
st.title("🏦 M&A Assessment — FastMCP + A2A")
st.caption(
    "Streamlit → A2A tasks/send (JSON-RPC 2.0) → Orchestrator "
    "→ A2A → Sub-Agents → FastMCP (stdio) → Tools"
)

# ── Sidebar: A2A agent discovery ─────────────────────────────────────────────
with st.sidebar:
    st.header("Agent Discovery (A2A)")
    if st.button("Discover Agents"):
        try:
            r = httpx.get(f"{ORCHESTRATOR_URL}/discover", timeout=5)
            data = r.json()
            for agent in [data["orchestrator"]] + data["sub_agents"]:
                with st.expander(f"📋 {agent['name']}"):
                    st.write(f"**URL:** `{agent['url']}`")
                    st.write(f"**Description:** {agent['description']}")
                    for skill in agent.get("skills", []):
                        st.write(f"**Skill:** {skill['name']} — {skill['description']}")
                    caps = agent.get("capabilities", {})
                    st.write(f"**Streaming:** {caps.get('streaming', False)}")
        except Exception as e:
            st.error(f"Cannot reach orchestrator: {e}\nMake sure all 3 servers are running.")

# ── Input form ────────────────────────────────────────────────────────────────
st.subheader("Deal Information")
col1, col2 = st.columns(2)

with col1:
    company_name = st.text_input("Target Company", "Acme Corp")
    industry = st.selectbox(
        "Industry",
        ["Technology", "Healthcare", "Manufacturing", "Telecom", "Defense", "Retail"],
    )
    employees = st.number_input("Employees", min_value=1, value=500)
    geography = st.text_input("Geography", "United States")

with col2:
    revenue = st.number_input("Revenue ($M)", min_value=0.0, value=50.0, step=5.0)
    ebitda = st.number_input("EBITDA ($M)", min_value=0.0, value=10.0, step=1.0)
    net_debt = st.number_input("Net Debt ($M)", min_value=0.0, value=20.0, step=5.0)
    deal_size = st.number_input("Deal Size ($M)", min_value=0.0, value=100.0, step=10.0)
    industry_multiple = st.number_input("EV/EBITDA Multiple", min_value=1.0, value=10.0, step=0.5)

notes = st.text_area("Notes", "Strong product, growing revenue, 3 years old")

# ── Run assessment ────────────────────────────────────────────────────────────
if st.button("🚀 Run Assessment", type="primary", use_container_width=True):

    # Build A2A tasks/send request
    a2a_request = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tasks/send",
        "params": {
            "id": str(uuid.uuid4()),
            "message": {
                "role": "user",
                "parts": [{
                    "type": "data",
                    "data": {
                        "company_name": company_name,
                        "financials": {
                            "revenue": revenue,
                            "ebitda": ebitda,
                            "net_debt": net_debt,
                            "industry_multiple": industry_multiple,
                        },
                        "profile": {
                            "industry": industry,
                            "employees": employees,
                            "deal_size_usd_millions": deal_size,
                            "geography": geography,
                            "notes": notes,
                        },
                    },
                }],
            },
        },
    }

    with st.spinner("Agents communicating via A2A + FastMCP…"):
        try:
            r = httpx.post(ORCHESTRATOR_URL, json=a2a_request, timeout=120)
            rpc_response = r.json()

            if "error" in rpc_response:
                st.error(f"A2A Error: {rpc_response['error']}")
            else:
                result = rpc_response["result"]
                st.caption(
                    f"Task status: `{result['status']['state']}`  |  "
                    f"Task ID: `{result['id']}`"
                )

                artifacts = {art["name"]: art["parts"][0] for art in result["artifacts"]}
                recommendation = artifacts["final_recommendation"]["text"]
                sub_data = artifacts["sub_agent_reports"]["data"]

                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "📋 Final Recommendation",
                    "💰 Financial Analysis",
                    "⚠️ Risk Assessment",
                    "🔧 MCP Tool Results",
                    "🔌 Protocol Trace",
                ])

                with tab1:
                    st.markdown(recommendation)

                with tab2:
                    st.markdown(sub_data["financial_analysis"])

                with tab3:
                    st.markdown(sub_data["risk_assessment"])

                with tab4:
                    st.subheader("Raw MCP tool outputs (FastMCP → JSON)")
                    st.json(sub_data["mcp_tool_results"])

                with tab5:
                    st.subheader("How messages flowed between processes")
                    for step, desc in sub_data["protocol_trace"].items():
                        st.markdown(f"**{step.replace('_', ' ').title()}**  \n`{desc}`")
                    st.divider()
                    st.caption("Raw A2A request sent to orchestrator:")
                    st.json(a2a_request)

        except httpx.ConnectError:
            st.error("Cannot connect to Orchestrator at :8000. Run ./start.sh first.")
        except Exception as e:
            st.error(f"Error: {e}")
