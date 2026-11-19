"""Deployable MCP server exposing Akeyless RTA/ARA tools on AgentCore.

Deploy with AgentCore CLI 1.x: use this file as app/agent/main.py, set
"protocol": "MCP" and "authorizerType": "AWS_IAM" on the runtime in
agentcore/agentcore.json, then run `agentcore deploy`. See docs/USER_GUIDE.md.

Or run locally (requires a Gateway with ARA enabled):
  AKEYLESS_GATEWAY_URL=https://gw.example.com:8000 \\
  AKEYLESS_ACCESS_ID=p-xxxxx AKEYLESS_ACCESS_TYPE=access_key AKEYLESS_ACCESS_KEY=... \\
    python server.py
"""

from akeyless_agentcore_rta.tools.mcp import run_mcp_server

if __name__ == "__main__":
    run_mcp_server()
