"""FastMCP server exposing Akeyless RTA/ARA tools for AgentCore Runtime."""

from __future__ import annotations

from typing import Any

from akeyless_agentcore_rta.tools.service import AraToolService

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "MCP support requires the 'mcp' package. "
        "Install with: pip install 'akeyless-agentcore-rta[mcp]'"
    ) from exc


def create_mcp_server(
    *,
    name: str = "akeyless-rta",
    service: AraToolService | None = None,
    host: str = "0.0.0.0",
    stateless_http: bool = True,
) -> FastMCP:
    """Create a FastMCP server with Akeyless ARA tools (no secret values)."""
    tool_service = service or AraToolService()
    mcp = FastMCP(name, host=host, stateless_http=stateless_http)

    @mcp.tool(name="list-secrets")
    def list_secrets(path: str | None = None) -> str:
        """List ARA-enabled Akeyless secrets and SSH certificate issuers your role can access. Returns metadata only, never values.

        Args:
            path: Optional folder path to scope the listing.
        """
        return tool_service.list_secrets(path=path).to_json()

    @mcp.tool(name="query-db")
    def query_db(
        payload: str,
        secret_name: str | None = None,
        agent_id: str | None = None,
        original_user: str | None = None,
        original_prompt: str | None = None,
        auth_code: str | None = None,
        state: str | None = None,
    ) -> str:
        """Execute a database query using Akeyless Runtime Authority (credentials stay on the Gateway).

        Supports MySQL, PostgreSQL, MSSQL, Oracle, Snowflake, HanaDB, Redshift, MongoDB, Redis, and Cassandra.
        Returns query results only — never credentials.

        Args:
            payload: SQL or DB command (e.g. SELECT * FROM users LIMIT 10).
            secret_name: Full Akeyless secret path (dynamic or rotated DB secret).
            agent_id: Agent identifier for auditing.
            original_user: Human end-user behind the agent (auditing).
            original_prompt: Original natural-language request (auditing).
            auth_code: OAuth auth code when retrying after an authorization challenge.
            state: OAuth state when retrying after an authorization challenge.
        """
        return tool_service.query_db(
            payload,
            secret_name=secret_name,
            agent_id=agent_id,
            original_user=original_user,
            original_prompt=original_prompt,
            auth_code=auth_code,
            state=state,
        ).to_json()

    @mcp.tool(name="service-execute")
    def service_execute(
        payload: str,
        secret_name: str | None = None,
        agent_id: str | None = None,
        original_user: str | None = None,
        original_prompt: str | None = None,
        auth_code: str | None = None,
        state: str | None = None,
    ) -> str:
        """Execute a cloud/K8s/GitHub/custom-MCP action, or run one non-interactive command on a remote host, via Akeyless Runtime Authority.

        Remote hosts: a shell command over SSH (SSH targets and SSH certificate issuers) or a
        PowerShell/CMD command over WinRM (Windows and LDAP items); the result has stdout,
        stderr, exit_code and cwd. To choose the host, the working directory or the shell, or to
        upload or download a file, send a sub-tool call as the payload, e.g.
        {"tool":"run","arguments":{"command":"<command>","host":"<host>"}}; list-sub-tools
        returns the remote sub-tools and their arguments.

        Credentials stay on the Gateway. Returns action results only.

        Args:
            payload: Natural language or CLI-style action for services, a literal command line
                (e.g. uptime, Get-Service) or a sub-tool call JSON for remote hosts.
            secret_name: Full Akeyless secret path for the service or remote item.
            agent_id: Agent identifier for auditing.
            original_user: Human end-user behind the agent (auditing).
            original_prompt: Original natural-language request (auditing).
            auth_code: OAuth auth code when retrying after an authorization challenge.
            state: OAuth state when retrying after an authorization challenge.
        """
        return tool_service.service_execute(
            payload,
            secret_name=secret_name,
            agent_id=agent_id,
            original_user=original_user,
            original_prompt=original_prompt,
            auth_code=auth_code,
            state=state,
        ).to_json()

    @mcp.tool(name="list-sub-tools")
    def list_sub_tools(
        secret_name: str | None = None,
        agent_id: str | None = None,
    ) -> str:
        """Optional: discover sub-tool names/parameters for a service secret or remote item (SSH, Windows, LDAP, SSH certificate issuers) before service-execute.

        Not required for database secrets (use query-db). Not required for service-execute
        when the payload is already clear.

        Args:
            secret_name: Full Akeyless service secret or remote item path.
            agent_id: Agent identifier for auditing.
        """
        return tool_service.list_sub_tools(
            secret_name=secret_name,
            agent_id=agent_id,
        ).to_json()

    return mcp


def run_mcp_server(**kwargs: Any) -> None:
    """Run the Akeyless RTA MCP server with streamable HTTP (AgentCore-compatible)."""
    create_mcp_server(**kwargs).run(transport="streamable-http")
