"""MCP server exposing Akeyless RTA/ARA tools for AgentCore Runtime.

Tool names, descriptions, parameter names and ``required`` lists are the Go MCP
server's (``gateway/ara/ara_mcp_tools.go``, served by ``akeyless
mcp-runtime-authority``), so an agent sees the same contract whichever ARA MCP
server it talks to. ``tests/test_mcp_tools.py`` pins the strings; when editing
one here, update the Go source (or vice versa).
"""

from __future__ import annotations

from typing import Any

from akeyless_agentcore_rta.tools.service import AraToolService, ToolResponse

try:
    import anyio.to_thread
    from mcp.server.fastmcp import FastMCP
    from mcp.types import TextContent
    from mcp.types import Tool as MCPTool
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "MCP support requires the 'mcp' package. "
        "Install with: pip install 'akeyless-agentcore-rta[mcp]'"
    ) from exc

# Matches remoteCallExample in gateway/ara/remote_call.go.
REMOTE_CALL_EXAMPLE = '{"tool":"run","arguments":{"command":"<command>","host":"<host>"}}'

AGENT_ID_DESCRIPTION = "Agent identifier for auditing purposes."
ORIGINAL_USER_DESCRIPTION = "The human end-user behind the agent (for auditing)."


def _query_db_tool(default_secret_name: str | None) -> MCPTool:
    """Matches NewQueryDBTool."""
    description = (
        "Execute a query against a database using Akeyless secret credentials (dynamic or rotated). "
        "Supports MySQL, PostgreSQL, MSSQL, Oracle, Snowflake, HanaDB, Redshift, MongoDB, Redis, and Cassandra. "
        "Returns the query results as a JSON array of objects."
    )
    if not default_secret_name:
        description += (
            " IMPORTANT: Always ask the user for the secret name if it was not provided in the conversation, "
            "you can use the list-secrets tool to get the list of available secrets."
        )
    properties: dict[str, Any] = {
        "payload": {
            "type": "string",
            "description": "The query or command to execute (e.g. SELECT * FROM users LIMIT 10).",
        },
        "agent-id": {"type": "string", "description": AGENT_ID_DESCRIPTION},
        "original-user": {"type": "string", "description": ORIGINAL_USER_DESCRIPTION},
        "original-prompt": {
            "type": "string",
            "description": "The user's original natural-language request before the agent translated it into a query.",
        },
    }
    required = ["payload", "agent-id", "original-user", "original-prompt"]
    if not default_secret_name:
        properties["secret-name"] = {
            "type": "string",
            "description": "Full path of the Akeyless secret — dynamic or rotated (e.g. /MyFolder/my-mysql-ds).",
        }
        required.append("secret-name")
    return MCPTool(
        name="query-db",
        description=description,
        inputSchema={"type": "object", "properties": properties, "required": required},
    )


def _service_execute_tool(default_secret_name: str | None) -> MCPTool:
    """Matches NewServiceExecuteTool."""
    description = (
        "Execute an action against a service (AWS, GCP, Azure, Kubernetes, or GitHub) using Akeyless secret "
        "credentials (dynamic or rotated), or run a single non-interactive command on a remote host: a shell "
        "command over SSH (SSH targets and SSH certificate issuers) or a PowerShell/CMD command over WinRM "
        "(Windows and LDAP items). "
        "A remote command returns stdout, stderr, exit_code and cwd. "
        "Accepts natural language or CLI-style payloads for services (e.g. 'list all S3 buckets', "
        "'kubectl get pods -n default', 'list open PRs') and a literal command line for remote hosts "
        "(e.g. 'uptime', 'Get-Service'). "
        "To choose the host, the working directory or the shell, or to upload or download a file, send a "
        f"remote item a sub-tool call as the payload, e.g. {REMOTE_CALL_EXAMPLE}; list-sub-tools returns the "
        "remote sub-tools and their arguments. "
        "Returns the results as JSON. Credentials are never exposed."
    )
    if not default_secret_name:
        description += (
            " IMPORTANT: Always ask the user for the secret name if it was not provided. "
            "Use the list-secrets tool to discover available secrets."
        )
    properties: dict[str, Any] = {
        "payload": {
            "type": "string",
            "description": "The action to execute. Can be natural language (e.g. 'list all S3 buckets') "
            "or CLI-style (e.g. 'aws s3 ls').",
        },
        "agent-id": {"type": "string", "description": AGENT_ID_DESCRIPTION},
        "auth-code": {
            "type": "string",
            "description": "OAuth authorization code returned after the user authorizes in the browser. "
            "Only required when the previous call returned an authorization URL.",
        },
        "state": {
            "type": "string",
            "description": "OAuth state parameter returned with the authorization URL. "
            "Must be passed back together with auth-code.",
        },
        "original-user": {"type": "string", "description": ORIGINAL_USER_DESCRIPTION},
        "original-prompt": {
            "type": "string",
            "description": "The user's original natural-language request before the agent translated it into an action.",
        },
    }
    required = ["payload", "agent-id", "original-user", "original-prompt"]
    if not default_secret_name:
        properties["secret-name"] = {
            "type": "string",
            "description": "Full path of the Akeyless secret — dynamic or rotated (e.g. /MyFolder/my-aws-ds).",
        }
        required.append("secret-name")
    return MCPTool(
        name="service-execute",
        description=description,
        inputSchema={"type": "object", "properties": properties, "required": required},
    )


def _list_secrets_tool() -> MCPTool:
    """Matches NewListSecretsTool, plus the connector's optional folder filter."""
    return MCPTool(
        name="list-secrets",
        description=(
            "List all supported secrets in the account — both dynamic and rotated "
            "(databases and services like AWS, GCP, Azure, Kubernetes, GitHub)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional Akeyless folder path to filter results (default /)",
                }
            },
            "required": [],
        },
    )


def _list_sub_tools_tool(default_secret_name: str | None) -> MCPTool:
    """Matches NewListSubToolsTool."""
    description = (
        "OPTIONAL helper for service secrets and remote items (SSH, Windows, LDAP, SSH certificate issuers); "
        "NOT for database secrets — query-db does not need this. "
        "Lists the sub-tools (and their parameters) that the service behind the given secret exposes. "
        "This call is never required: service-execute already accepts natural language or CLI-style payloads. "
        "Use it only when you want to discover the exact sub-tool name and parameters before calling "
        "service-execute, "
        "e.g. 1) list-secrets, 2) (optional) list-sub-tools with the chosen service secret, "
        "3) service-execute with a payload that invokes the chosen sub-tool with its required parameters."
    )
    properties: dict[str, Any] = {
        "agent-id": {
            "type": "string",
            "description": "Agent identifier for auditing and session-scoped credential caching.",
        }
    }
    required = ["agent-id"]
    if not default_secret_name:
        properties["secret-name"] = {
            "type": "string",
            "description": "Full path of the Akeyless secret. Must be a service secret (e.g. AWS, GCP, Azure, "
            "Kubernetes, GitHub, custom MCP) — not a database secret.",
        }
        required.append("secret-name")
    return MCPTool(
        name="list-sub-tools",
        description=description,
        inputSchema={"type": "object", "properties": properties, "required": required},
    )


def build_tool_definitions(default_secret_name: str | None) -> list[MCPTool]:
    """Tool list in the order of addTools in mcp_runtime_authority.go.

    list-secrets is only registered without a default secret, like Go.
    """
    tools = [
        _query_db_tool(default_secret_name),
        _service_execute_tool(default_secret_name),
        _list_sub_tools_tool(default_secret_name),
    ]
    if not default_secret_name:
        tools.append(_list_secrets_tool())
    return tools


class _ArgumentError(ValueError):
    pass


def _require_string(args: dict[str, Any], key: str) -> str:
    """Same checks and messages as mcp-go's CallToolRequest.RequireString."""
    if key not in args:
        raise _ArgumentError(f'required argument "{key}" not found')
    value = args[key]
    if not isinstance(value, str):
        raise _ArgumentError(f'argument "{key}" is not a string')
    return value


def _optional_string(args: dict[str, Any], key: str) -> str | None:
    value = args.get(key)
    return value if isinstance(value, str) and value else None


def _oauth_callback_args(args: dict[str, Any]) -> tuple[str | None, str | None]:
    """Same rules and messages as extractOAuthCallbackArgs in mcp_runtime_authority.go."""
    has_auth_code = "auth-code" in args
    has_state = "state" in args
    if not has_auth_code and not has_state:
        return None, None
    if has_auth_code != has_state:
        missing = "state" if has_auth_code else "auth-code"
        raise _ArgumentError(f'OAuth callback parameters must be provided together: "{missing}" is missing')
    auth_code, state = args["auth-code"], args["state"]
    if not isinstance(auth_code, str):
        raise _ArgumentError(f'OAuth callback parameter "auth-code" must be a string, got {type(auth_code).__name__}')
    if not isinstance(state, str):
        raise _ArgumentError(f'OAuth callback parameter "state" must be a string, got {type(state).__name__}')
    if not auth_code or not state:
        raise _ArgumentError('OAuth callback parameters "auth-code" and "state" must both be non-empty')
    return auth_code, state


def handle_tool_call(
    service: AraToolService,
    name: str,
    arguments: dict[str, Any] | None,
    default_secret_name: str | None = None,
) -> str:
    """Dispatch one MCP tool call the way the Go handlers do; returns the JSON reply."""
    args = arguments or {}
    try:
        if name == "list-secrets" and not default_secret_name:
            return service.list_secrets(path=_optional_string(args, "path")).to_json()

        if name in ("query-db", "service-execute"):
            secret_name = default_secret_name or _require_string(args, "secret-name")
            payload = _require_string(args, "payload")
            agent_id = _require_string(args, "agent-id")
            auth_code, state = _oauth_callback_args(args)
            execute = service.query_db if name == "query-db" else service.service_execute
            return execute(
                payload,
                secret_name=secret_name,
                agent_id=agent_id,
                original_user=_optional_string(args, "original-user"),
                original_prompt=_optional_string(args, "original-prompt"),
                auth_code=auth_code,
                state=state,
            ).to_json()

        if name == "list-sub-tools":
            secret_name = default_secret_name or _require_string(args, "secret-name")
            agent_id = _require_string(args, "agent-id")
            return service.list_sub_tools(secret_name=secret_name, agent_id=agent_id).to_json()

        raise _ArgumentError(f"Unknown tool: {name}")
    except _ArgumentError as exc:
        return ToolResponse(ok=False, data={}, error=str(exc)).to_json()


class AraFastMCP(FastMCP):
    """FastMCP with the Go tool definitions instead of schemas derived from Python signatures."""

    def __init__(self, name: str, *, service: AraToolService, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._ara_service = service
        self._default_secret_name = service.client.config.default_secret_name

    async def list_tools(self) -> list[MCPTool]:
        return build_tool_definitions(self._default_secret_name)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        text = await anyio.to_thread.run_sync(
            handle_tool_call, self._ara_service, name, arguments, self._default_secret_name
        )
        return [TextContent(type="text", text=text)]


def create_mcp_server(
    *,
    name: str = "akeyless-rta",
    service: AraToolService | None = None,
    host: str = "0.0.0.0",
    stateless_http: bool = True,
) -> AraFastMCP:
    """Create the MCP server with the Akeyless ARA tools (no secret values)."""
    return AraFastMCP(
        name,
        service=service or AraToolService(),
        host=host,
        stateless_http=stateless_http,
    )


def run_mcp_server(**kwargs: Any) -> None:
    """Run the Akeyless RTA MCP server with streamable HTTP (AgentCore-compatible)."""
    create_mcp_server(**kwargs).run(transport="streamable-http")
