#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON=".venv/bin/python"
STREAMLIT=".venv/bin/streamlit"

if [ ! -f "$PYTHON" ]; then
  echo "ERROR: .venv not found. Run: uv sync"
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "ERROR: .env file missing. Create it with: ANTHROPIC_API_KEY=sk-ant-..."
  exit 1
fi

# Kill any previous instances
pkill -f "financial_agent.py" 2>/dev/null || true
pkill -f "risk_agent.py"      2>/dev/null || true
pkill -f "orchestrator.py"    2>/dev/null || true
pkill -f "streamlit run app"  2>/dev/null || true
sleep 1

echo "Starting Financial Agent  → http://localhost:8001"
"$PYTHON" financial_agent.py > /tmp/financial_agent.log 2>&1 &

echo "Starting Risk Agent       → http://localhost:8002"
"$PYTHON" risk_agent.py > /tmp/risk_agent.log 2>&1 &

# Give sub-agents a moment to bind their ports
sleep 2

echo "Starting Orchestrator     → http://localhost:8000"
"$PYTHON" orchestrator.py > /tmp/orchestrator.log 2>&1 &

sleep 1

echo "Starting Streamlit UI     → http://localhost:8501"
"$STREAMLIT" run app.py --server.port 8501 2>&1 &

echo ""
echo "All services running."
echo "  Streamlit UI      →  http://localhost:8501"
echo "  Orchestrator card →  http://localhost:8000/.well-known/agent.json"
echo ""
echo "Logs: /tmp/financial_agent.log | /tmp/risk_agent.log | /tmp/orchestrator.log"
echo "Stop: ./stop.sh"

wait
