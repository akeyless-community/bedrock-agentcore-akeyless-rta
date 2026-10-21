"""AgentCore tool integrations for Akeyless RTA/ARA."""

from akeyless_agentcore_rta.tools.service import AraToolService

__all__ = [
    "AraToolService",
    "create_mcp_server",
    "run_mcp_server",
]


def __getattr__(name: str):
    if name in ("create_mcp_server", "run_mcp_server"):
        from akeyless_agentcore_rta.tools.mcp import create_mcp_server, run_mcp_server

        return {"create_mcp_server": create_mcp_server, "run_mcp_server": run_mcp_server}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
