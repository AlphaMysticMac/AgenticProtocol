#!/usr/bin/env bash
pkill -f "financial_agent.py" 2>/dev/null && echo "Stopped Financial Agent"  || echo "Financial Agent not running"
pkill -f "risk_agent.py"      2>/dev/null && echo "Stopped Risk Agent"        || echo "Risk Agent not running"
pkill -f "orchestrator.py"    2>/dev/null && echo "Stopped Orchestrator"      || echo "Orchestrator not running"
pkill -f "streamlit run app"  2>/dev/null && echo "Stopped Streamlit UI"      || echo "Streamlit not running"
