import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from akeyless_agentcore_rta.client import AkeylessRtaClient
from akeyless_agentcore_rta.tools.mcp import create_mcp_server
from akeyless_agentcore_rta.tools.service import AraToolService


def test_mcp_registers_four_ara_tools_only():
    api = MagicMock()
    client = AkeylessRtaClient(
        gateway_input_url="https://gw.example.com:8000",
        token="t-fixed",
        _api=api,
    )
    server = create_mcp_server(service=AraToolService(client=client))
    names = set(server._tool_manager._tools.keys())
    assert names == {"list-secrets", "query-db", "service-execute", "list-sub-tools"}
    assert "get_akeyless_secret" not in names
    assert "get-secret" not in names


def test_list_secrets_tool_json_has_no_values():
    api = MagicMock()
    api.list_items.return_value = SimpleNamespace(
        items=[
            {
                "item_name": "/db/pg",
                "item_type": "dynamic-secret",
                "client_permissions": ["ara_allow_access"],
                "dynamic_secret_producer_details": {"producer_type": "postgres"},
            }
        ]
    )
    client = AkeylessRtaClient(
        gateway_input_url="https://gw.example.com:8000",
        token="t-fixed",
        _api=api,
    )
    service = AraToolService(client=client)
    payload = json.loads(service.list_secrets().to_json())
    assert payload["ok"] is True
    assert payload["secrets"][0]["name"] == "/db/pg"
    assert "value" not in payload["secrets"][0]
