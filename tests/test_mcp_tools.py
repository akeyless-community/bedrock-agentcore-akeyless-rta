"""Pins the MCP tool contract to the Go MCP server (gateway/ara/ara_mcp_tools.go and
client/commands/mcp_runtime_authority.go). If these fail, this package or the Go
source drifted — update whichever is stale."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import anyio
import pytest

from akeyless_agentcore_rta.ara import OAuthAuthorizationRequiredError
from akeyless_agentcore_rta.client import AkeylessRtaClient
from akeyless_agentcore_rta.tools.mcp import (
    build_tool_definitions,
    create_mcp_server,
    handle_tool_call,
)
from akeyless_agentcore_rta.tools.service import AraToolService, ToolResponse

EXECUTE_REQUIRED = ["payload", "agent-id", "original-user", "original-prompt", "secret-name"]


def _client(**kwargs) -> AkeylessRtaClient:
    return AkeylessRtaClient(
        gateway_input_url="https://gw.example.com:8000",
        token="t-fixed",
        _api=MagicMock(),
        **kwargs,
    )


def _service() -> MagicMock:
    service = MagicMock(spec=AraToolService)
    ok = ToolResponse(ok=True, data={"results": []})
    service.query_db.return_value = ok
    service.service_execute.return_value = ok
    service.list_sub_tools.return_value = ok
    service.list_secrets.return_value = ok
    return service


def _call(service, name, args, default_secret_name=None) -> dict:
    return json.loads(handle_tool_call(service, name, args, default_secret_name))


class TestToolDefinitions:
    def setup_method(self):
        self.by_name = {t.name: t for t in build_tool_definitions(None)}

    def test_tools_in_go_order(self):
        assert [t.name for t in build_tool_definitions(None)] == [
            "query-db",
            "service-execute",
            "list-sub-tools",
            "list-secrets",
        ]

    def test_query_db_matches_new_query_db_tool(self):
        tool = self.by_name["query-db"]
        assert tool.description == (
            "Execute a query against a database using Akeyless secret credentials (dynamic or rotated). "
            "Supports MySQL, PostgreSQL, MSSQL, Oracle, Snowflake, HanaDB, Redshift, MongoDB, Redis, and Cassandra. "
            "Returns the query results as a JSON array of objects. "
            "IMPORTANT: Always ask the user for the secret name if it was not provided in the conversation, "
            "you can use the list-secrets tool to get the list of available secrets."
        )
        props = tool.inputSchema["properties"]
        assert set(props) == {"payload", "agent-id", "original-user", "original-prompt", "secret-name"}
        assert props["secret-name"]["description"] == (
            "Full path of the Akeyless secret — dynamic or rotated (e.g. /MyFolder/my-mysql-ds)."
        )
        assert props["payload"]["description"] == (
            "The query or command to execute (e.g. SELECT * FROM users LIMIT 10)."
        )
        assert props["original-prompt"]["description"] == (
            "The user's original natural-language request before the agent translated it into a query."
        )
        assert tool.inputSchema["required"] == EXECUTE_REQUIRED

    def test_service_execute_matches_new_service_execute_tool(self):
        tool = self.by_name["service-execute"]
        assert tool.description == (
            "Execute an action against a service (AWS, GCP, Azure, Kubernetes, or GitHub) using Akeyless secret credentials (dynamic or rotated), "
            "or run a single non-interactive command on a remote host: a shell command over SSH (SSH targets and SSH certificate issuers) or a PowerShell/CMD command over WinRM (Windows and LDAP items). "
            "A remote command returns stdout, stderr, exit_code and cwd. "
            "Accepts natural language or CLI-style payloads for services (e.g. 'list all S3 buckets', 'kubectl get pods -n default', 'list open PRs') and a literal command line for remote hosts (e.g. 'uptime', 'Get-Service'). "
            "To choose the host, the working directory or the shell, or to upload or download a file, send a remote item a sub-tool call as the payload, e.g. "
            '{"tool":"run","arguments":{"command":"<command>","host":"<host>"}}; list-sub-tools returns the remote sub-tools and their arguments. '
            "Returns the results as JSON. Credentials are never exposed. "
            "IMPORTANT: Always ask the user for the secret name if it was not provided. Use the list-secrets tool to discover available secrets."
        )
        props = tool.inputSchema["properties"]
        assert set(props) == {
            "payload",
            "agent-id",
            "auth-code",
            "state",
            "original-user",
            "original-prompt",
            "secret-name",
        }
        assert props["auth-code"]["description"] == (
            "OAuth authorization code returned after the user authorizes in the browser. "
            "Only required when the previous call returned an authorization URL."
        )
        assert tool.inputSchema["required"] == EXECUTE_REQUIRED

    def test_list_sub_tools_matches_new_list_sub_tools_tool(self):
        tool = self.by_name["list-sub-tools"]
        assert tool.description.startswith(
            "OPTIONAL helper for service secrets and remote items (SSH, Windows, LDAP, SSH certificate issuers); "
            "NOT for database secrets — query-db does not need this. "
        )
        assert set(tool.inputSchema["properties"]) == {"agent-id", "secret-name"}
        assert tool.inputSchema["required"] == ["agent-id", "secret-name"]

    def test_list_secrets_matches_new_list_secrets_tool(self):
        assert self.by_name["list-secrets"].description == (
            "List all supported secrets in the account — both dynamic and rotated "
            "(databases and services like AWS, GCP, Azure, Kubernetes, GitHub)."
        )

    def test_default_secret_drops_secret_name_and_list_secrets(self):
        tools = build_tool_definitions("/prod/db/pg")
        assert [t.name for t in tools] == ["query-db", "service-execute", "list-sub-tools"]
        for tool in tools:
            assert "secret-name" not in tool.inputSchema["properties"]
            assert "secret-name" not in tool.inputSchema["required"]
            assert "IMPORTANT" not in tool.description


class TestHandleToolCall:
    @pytest.mark.parametrize("tool", ["query-db", "service-execute"])
    def test_forwards_go_parameter_names(self, tool):
        service = _service()
        _call(
            service,
            tool,
            {
                "secret-name": "/srv/ssh",
                "payload": "uptime",
                "agent-id": "agent-1",
                "original-user": "alice",
                "original-prompt": "is web1 up?",
            },
        )
        getattr(service, tool.replace("-", "_")).assert_called_once_with(
            "uptime",
            secret_name="/srv/ssh",
            agent_id="agent-1",
            original_user="alice",
            original_prompt="is web1 up?",
            auth_code=None,
            state=None,
        )

    @pytest.mark.parametrize(
        ("tool", "args", "missing"),
        [
            ("query-db", {"payload": "SELECT 1", "agent-id": "a"}, "secret-name"),
            ("query-db", {"secret-name": "/db", "agent-id": "a"}, "payload"),
            ("service-execute", {"secret-name": "/srv", "payload": "uptime"}, "agent-id"),
            ("list-sub-tools", {"secret-name": "/srv"}, "agent-id"),
            ("list-sub-tools", {"agent-id": "a"}, "secret-name"),
        ],
    )
    def test_required_arguments_like_require_string(self, tool, args, missing):
        service = _service()
        out = _call(service, tool, args)
        assert out == {"ok": False, "error": f'required argument "{missing}" not found'}
        service.query_db.assert_not_called()
        service.service_execute.assert_not_called()
        service.list_sub_tools.assert_not_called()

    def test_default_secret_overrides_secret_name(self):
        service = _service()
        _call(service, "service-execute", {"secret-name": "/other", "payload": "x", "agent-id": "a"}, "/default")
        assert service.service_execute.call_args.kwargs["secret_name"] == "/default"

    def test_oauth_callback_args_must_come_together(self):
        out = _call(
            _service(),
            "service-execute",
            {"secret-name": "/gh", "payload": "x", "agent-id": "a", "auth-code": "c"},
        )
        assert out["error"] == 'OAuth callback parameters must be provided together: "state" is missing'

    def test_oauth_callback_args_forwarded(self):
        service = _service()
        _call(
            service,
            "service-execute",
            {"secret-name": "/gh", "payload": "x", "agent-id": "a", "auth-code": "c", "state": "s"},
        )
        kwargs = service.service_execute.call_args.kwargs
        assert (kwargs["auth_code"], kwargs["state"]) == ("c", "s")

    def test_list_secrets_hidden_with_default_secret(self):
        out = _call(_service(), "list-secrets", {}, "/default")
        assert out == {"ok": False, "error": "Unknown tool: list-secrets"}


class TestListSubToolsOAuth:
    def test_points_at_service_execute_like_go(self):
        client = _client()
        client.list_sub_tools = MagicMock(
            side_effect=OAuthAuthorizationRequiredError("https://auth.example.com/authorize", "state-123")
        )
        out = json.loads(AraToolService(client=client).list_sub_tools(secret_name="/gh", agent_id="a").to_json())
        assert out["ok"] is False
        assert out["state"] == "state-123"
        assert out["error"] == (
            "This secret requires OAuth authorization. "
            "Please open the following URL in your browser to authorize, "
            "then call service-execute with the auth-code and state parameters to complete the flow.\n\n"
            "Authorization URL: https://auth.example.com/authorize\nState: state-123"
        )


class TestServer:
    def test_lists_go_tools(self):
        server = create_mcp_server(service=AraToolService(client=_client()))
        tools = anyio.run(server.list_tools)
        assert [t.name for t in tools] == ["query-db", "service-execute", "list-sub-tools", "list-secrets"]

    def test_default_secret_from_client_config(self):
        server = create_mcp_server(service=AraToolService(client=_client(default_secret_name="/prod/db")))
        tools = anyio.run(server.list_tools)
        assert "list-secrets" not in [t.name for t in tools]

    def test_call_tool_returns_json_text_without_values(self):
        client = _client()
        client._api.list_items.return_value = SimpleNamespace(
            items=[
                {
                    "item_name": "/db/pg",
                    "item_type": "dynamic-secret",
                    "client_permissions": ["ara_allow_access"],
                    "dynamic_secret_producer_details": {"producer_type": "postgres"},
                }
            ]
        )
        server = create_mcp_server(service=AraToolService(client=client))
        content = anyio.run(server.call_tool, "list-secrets", {})
        payload = json.loads(content[0].text)
        assert payload["ok"] is True
        assert payload["secrets"][0]["name"] == "/db/pg"
        assert "value" not in payload["secrets"][0]
