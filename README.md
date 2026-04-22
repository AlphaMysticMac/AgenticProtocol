# M&A Intelligence Agent System

An agentic AI system for Merger & Acquisition analysis, demonstrating real **MCP (Model Context Protocol)** and **A2A (Agent-to-Agent)** communication patterns.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit UI  :8501                          │
│                     (A2A Client — browser)                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │  HTTP POST /
                             │  A2A tasks/send  (JSON-RPC 2.0)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Orchestrator Agent  :8000                             │
│   GET  /.well-known/agent.json   →  A2A agent card                 │
│   GET  /discover                 →  fetch sub-agent cards           │
│   POST /                         →  tasks/send handler              │
│                                                                     │
│   Synthesizes sub-agent reports with Claude (claude-sonnet-4-6)     │
└────────────┬──────────────────────────────────┬─────────────────────┘
             │  HTTP POST /                      │  HTTP POST /
             │  A2A tasks/send                   │  A2A tasks/send
             ▼                                   ▼
┌────────────────────────────┐    ┌──────────────────────────────────┐
│  Financial Agent  :8001    │    │  Risk Agent  :8002               │
│  /.well-known/agent.json   │    │  /.well-known/agent.json         │
│                            │    │                                  │
│  MCP tools used:           │    │  MCP tools used:                 │
│  • calculate_valuation     │    │  • flag_regulatory_risk          │
│  • assess_debt_ratio       │    │                                  │
└────────────┬───────────────┘    └──────────────┬───────────────────┘
             │  stdio spawn                       │  stdio spawn
             │  MCP SDK (stdio_client)            │  MCP SDK (stdio_client)
             ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    mcp_server.py  (FastMCP subprocess)              │
│                                                                     │
│   @mcp.tool() calculate_valuation(ebitda, multiple)                 │
│   @mcp.tool() assess_debt_ratio(net_debt, ebitda)                   │
│   @mcp.tool() flag_regulatory_risk(industry, deal_size)             │
│                                                                     │
│   Transport: JSON-RPC 2.0 over stdin / stdout (MCP SDK)             │
└─────────────────────────────────────────────────────────────────────┘
```

### Protocol layers

| Layer | Protocol | Transport |
|---|---|---|
| UI → Orchestrator | A2A `tasks/send` | HTTP POST, JSON-RPC 2.0 |
| Orchestrator → Sub-agents | A2A `tasks/send` | HTTP POST, JSON-RPC 2.0 |
| Sub-agents → MCP server | MCP `tools/call` | `stdio_client` + `ClientSession` (MCP SDK) |
| MCP server tools | Python functions | Decorated with `@mcp.tool()` via FastMCP |

---

## Project structure

```
ma_agent/
│
├── mcp_server.py          # FastMCP tool server — spawned as a subprocess by agents
│                          # Tools: calculate_valuation, assess_debt_ratio, flag_regulatory_risk
│
├── financial_agent.py     # A2A server on :8001
│                          # Calls MCP tools via stdio_client + ClientSession
│                          # Interprets results with Claude
│
├── risk_agent.py          # A2A server on :8002
│                          # Calls MCP regulatory tool via stdio_client + ClientSession
│                          # Interprets results with Claude
│
├── orchestrator.py        # A2A server on :8000
│                          # Delegates to financial + risk agents via A2A tasks/send
│                          # Synthesizes final recommendation with Claude
│
├── app.py                 # Streamlit UI — sends A2A tasks/send to orchestrator
│                          # Displays artifacts: recommendation, analyses, MCP results, trace
│
├── agent_cards/           # Reference A2A agent card JSON files
│   ├── orchestrator_card.json
│   ├── financial_card.json
│   └── risk_card.json
│
├── start.sh               # Starts all 4 services (3 FastAPI agents + Streamlit)
├── stop.sh                # Kills all running services
│
├── pyproject.toml         # Project dependencies (managed by uv)
├── uv.lock                # Locked dependency versions
├── .env                   # API keys (not committed) — see setup below
└── .venv/                 # Virtual environment created by uv
```

---

## Installation

### 1. Install uv

`uv` is a fast Python package and project manager (replaces pip + venv).

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Homebrew (macOS):**
```bash
brew install uv
```

Verify:
```bash
uv --version
```

---

### 2. Clone the repository

```bash
git clone <repo-url>
cd ma_agent
```

---

### 3. Create the virtual environment and install dependencies

```bash
uv sync
```

This reads `pyproject.toml`, creates `.venv/`, and installs all dependencies in one step. No `pip install` needed.

---

### 4. Set your Anthropic API key

Create a `.env` file in the project root:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

Get your key at [console.anthropic.com](https://console.anthropic.com).

---

### 5. Run the system

```bash
./start.sh
```

This starts all four services:

| Service | Port | Role |
|---|---|---|
| Orchestrator | 8000 | A2A coordinator |
| Financial Agent | 8001 | Valuation + debt analysis |
| Risk Agent | 8002 | Regulatory + risk analysis |
| Streamlit UI | 8501 | Browser interface |

Open **http://localhost:8501** in your browser.

To stop all services:
```bash
./stop.sh
```

---

## A2A agent cards

Each agent exposes its identity at the standard A2A well-known path:

```
http://localhost:8000/.well-known/agent.json   ← Orchestrator
http://localhost:8001/.well-known/agent.json   ← Financial Agent
http://localhost:8002/.well-known/agent.json   ← Risk Agent
```

All registered agents can be discovered at once:

```bash
curl http://localhost:8000/discover
```

---

## How a single assessment works

1. Streamlit sends an `A2A tasks/send` (JSON-RPC 2.0) to the Orchestrator with the deal payload.
2. Orchestrator fans out two parallel `A2A tasks/send` calls — one to the Financial Agent, one to the Risk Agent.
3. Each sub-agent spawns `mcp_server.py` as a subprocess and calls tools via the MCP SDK (`stdio_client` + `ClientSession`).
4. FastMCP tools execute (`calculate_valuation`, `assess_debt_ratio`, `flag_regulatory_risk`) and return JSON results.
5. Each sub-agent passes the raw tool output to Claude for natural-language interpretation, then returns an A2A response with typed `artifacts`.
6. Orchestrator synthesizes both reports with Claude and returns a final recommendation artifact.
7. Streamlit renders the recommendation, per-agent analyses, raw MCP outputs, and the full protocol trace.

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | Claude API client |
| `mcp` | MCP SDK — `FastMCP` server + `stdio_client` / `ClientSession` |
| `fastapi` + `uvicorn` | A2A HTTP servers |
| `httpx` | A2A HTTP client (async + sync) |
| `streamlit` | Browser UI |
| `python-dotenv` | Load `ANTHROPIC_API_KEY` from `.env` |
