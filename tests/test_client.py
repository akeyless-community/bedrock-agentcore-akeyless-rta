import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from akeyless_agentcore_rta.ara import OAuthAuthorizationRequiredError
from akeyless_agentcore_rta.client import AkeylessRtaClient
from akeyless_agentcore_rta.http_ara import post_ara_json


def _client(**kwargs) -> AkeylessRtaClient:
    api = MagicMock()
    return AkeylessRtaClient(
        gateway_input_url="https://gw.example.com:8000",
        access_type="access_key",
        access_id="p-test",
        access_key="k-test",
        token="t-fixed",
        _api=api,
        **kwargs,
    )


class TestListSecrets:
    def test_returns_metadata_only(self):
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
        secrets = client.list_secrets()
        assert len(secrets) == 1
        assert secrets[0].name == "/db/pg"
        assert secrets[0].target_type == "postgres"
        call_arg = client._api.list_items.call_args[0][0]
        assert call_arg.ara_only is True


class TestExecute:
    def test_query_db_posts_target_query(self):
        captured: dict = {}

        def opener(request, timeout=120):  # noqa: ARG001
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode())
            captured["auth"] = request.get_header("Authorization")
            return io.BytesIO(
                json.dumps(
                    {"target_type": "postgres", "results": [{"n": 1}]}
                ).encode()
            )

        # urlopen context manager shim
        class _Resp:
            def __init__(self, data: bytes):
                self._data = data
                self.status = 200

            def read(self):
                return self._data

            def getcode(self):
                return 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def cm_opener(request, timeout=120):  # noqa: ARG001
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode())
            captured["auth"] = request.get_header("Authorization")
            return _Resp(
                json.dumps({"target_type": "postgres", "results": [{"n": 1}]}).encode()
            )

        client = _client(_http_opener=cm_opener)
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
        result = client.query_db("SELECT 1", secret_name="/db/pg", agent_id="agent-1")
        assert captured["url"] == "https://gw.example.com:8000/config/target_query"
        assert captured["body"]["secret_name"] == "/db/pg"
        assert captured["body"]["payload"] == "SELECT 1"
        assert captured["body"]["agent_id"] == "agent-1"
        assert captured["body"]["mcp_id"] == "akeyless-agentcore-rta"
        assert captured["auth"] == "Bearer t-fixed"
        assert result.results == [{"n": 1}]
        assert result.target_type == "postgres"

    def test_rejects_service_secret_for_query_db(self):
        client = _client()
        client._api.list_items.return_value = SimpleNamespace(
            items=[
                {
                    "item_name": "/svc/aws",
                    "item_type": "dynamic-secret",
                    "client_permissions": ["ara_allow_access"],
                    "dynamic_secret_producer_details": {"producer_type": "aws"},
                }
            ]
        )
        with pytest.raises(ValueError, match="not a database secret"):
            client.query_db("list buckets", secret_name="/svc/aws")


class _JsonResp:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode()
        self.status = 200

    def read(self):
        return self._data

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestRemoteCommands:
    @pytest.mark.parametrize(
        "item",
        [
            {"item_name": "/srv/ssh", "item_type": "rotated-secret", "item_targets_assoc": [{"target_type": "ssh"}]},
            {"item_name": "/srv/rdp", "item_type": "dynamic-secret", "dynamic_secret_producer_details": {"producer_type": "rdp"}},
            {"item_name": "/ad/ldap", "item_type": "rotated-secret", "item_targets_assoc": [{"target_type": "ldap"}]},
            {"item_name": "/ssh/ca", "item_type": "SSH_CERT_ISSUER"},
        ],
    )
    def test_service_execute_forwards_remote_payload(self, item):
        captured: dict = {}

        def opener(request, timeout=None):
            captured["body"] = json.loads(request.data.decode())
            captured["timeout"] = timeout
            return _JsonResp(
                {"target_type": "ssh", "results": [{"stdout": "up", "stderr": "", "exit_code": 0, "truncated": False}]}
            )

        client = _client(_http_opener=opener)
        client._api.list_items.return_value = SimpleNamespace(
            items=[{**item, "client_permissions": ["ara_allow_access"]}]
        )
        payload = '{"tool":"run","arguments":{"command":"uptime","host":"3.12.101.6"}}'
        result = client.service_execute(payload, secret_name=item["item_name"])

        assert captured["body"]["secret_name"] == item["item_name"]
        assert captured["body"]["payload"] == payload
        assert captured["timeout"] == 270
        assert result.results[0]["exit_code"] == 0

    def test_query_db_points_remote_items_to_service_execute(self):
        client = _client()
        client._api.list_items.return_value = SimpleNamespace(
            items=[
                {
                    "item_name": "/srv/ssh",
                    "item_type": "rotated-secret",
                    "client_permissions": ["ara_allow_access"],
                    "item_targets_assoc": [{"target_type": "ssh"}],
                }
            ]
        )
        with pytest.raises(ValueError, match="Use service_execute instead"):
            client.query_db("uptime", secret_name="/srv/ssh")

    def test_list_secrets_requests_ssh_cert_issuers(self):
        client = _client()
        client._api.list_items.return_value = SimpleNamespace(items=[])
        client.list_secrets()
        assert "ssh-cert-issuer" in client._api.list_items.call_args[0][0].type


class TestOAuth:
    def test_401_oauth_challenge(self):
        class _HTTPError(Exception):
            def __init__(self):
                self.code = 401

            def read(self):
                return json.dumps(
                    {
                        "authorization_url": "https://idp.example/auth",
                        "state": "st-1",
                    }
                ).encode()

        import urllib.error

        def opener(request, timeout=120):  # noqa: ARG001
            err = urllib.error.HTTPError(
                url="https://gw.example.com:8000/config/target_query",
                code=401,
                msg="Unauthorized",
                hdrs=None,  # type: ignore[arg-type]
                fp=io.BytesIO(
                    json.dumps(
                        {
                            "authorization_url": "https://idp.example/auth",
                            "state": "st-1",
                        }
                    ).encode()
                ),
            )
            raise err

        with pytest.raises(OAuthAuthorizationRequiredError) as ei:
            post_ara_json(
                "https://gw.example.com:8000",
                "/config/target_query",
                {"Authorization": "Bearer t"},
                {"secret_name": "/x", "payload": "y"},
                "target query",
                opener=opener,
            )
        assert ei.value.authorization_url == "https://idp.example/auth"
        assert ei.value.state == "st-1"
