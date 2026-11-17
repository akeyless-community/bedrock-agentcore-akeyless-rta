import urllib.error

import pytest

from akeyless_agentcore_rta.browser_auth import build_auth_url, exchange_auth_code
from akeyless_agentcore_rta.config import config_from_env, validate_config
from akeyless_agentcore_rta.auth import AuthSession, build_gateway_auth_header
import base64
import json


class TestOidcConfig:
    def test_accepts_oidc_access_type(self):
        cfg = config_from_env(
            gateway_input_url="https://gw.example.com:8000",
            access_type="oidc",
            access_id="p-test",
        )
        validate_config(cfg)
        assert cfg.access_type == "oidc"

    def test_accepts_saml_access_type(self):
        cfg = config_from_env(
            gateway_input_url="https://gw.example.com:8000",
            access_type="saml",
            access_id="p-test",
        )
        validate_config(cfg)
        assert cfg.access_type == "saml"


class TestBuildAuthUrl:
    def test_oidc_url(self):
        url = build_auth_url(
            "https://gw.example.com:8000",
            "oidc",
            "p-abc123",
            "http://127.0.0.1:11137",
        )
        assert url.startswith("https://gw.example.com:8000/api/oidc-login?")
        assert "access_id=p-abc123" in url
        assert "product=ara" in url
        assert "is_use_short_token=true" in url
        assert "response_mode=auth_code" in url
        assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A11137" in url


class TestGatewayAuthHeader:
    def test_token_bearer(self):
        header = build_gateway_auth_header(AuthSession(token="t-1", expires_at=0))
        assert header == {"Authorization": "Bearer t-1"}

    def test_creds_base64_json(self):
        creds = {"token": "t-1", "access_id": "p-x"}
        header = build_gateway_auth_header(
            AuthSession(token="t-1", expires_at=0, creds=creds)
        )
        raw = header["Authorization"].removeprefix("Bearer ")
        decoded = json.loads(base64.b64decode(raw).decode("utf-8"))
        assert decoded == creds


class _Resp:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestExchangeAuthCode:
    def test_posts_code_and_converts_expires_at_to_ms(self):
        captured = {}

        def opener(request, timeout=None):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode())
            return _Resp({"token": "t-short", "expires_at": 1_900_000_000})

        result = exchange_auth_code("https://gw.example.com:8000/", "code-1", opener=opener)
        assert captured["url"] == "https://gw.example.com:8000/api/exchange-auth-code"
        assert captured["body"] == {"auth_code": "code-1"}
        assert result.token == "t-short"
        assert result.expiration == "1900000000000"

    def test_rejected_code(self):
        def opener(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

        with pytest.raises(RuntimeError, match=r"Auth code exchange failed \(401\)"):
            exchange_auth_code("https://gw.example.com:8000", "bad", opener=opener)


class TestCallbackAuthCode:
    """Runs the real callback server and sends the browser's redirect to it."""

    @staticmethod
    def _free_port() -> int:
        import socket

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _login(self, monkeypatch, query: str, exchange):
        import urllib.request

        from akeyless_agentcore_rta import browser_auth

        port = self._free_port()
        seen: dict = {}

        def fake_browser(url):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/?{query}", timeout=5) as resp:
                    seen["status"], seen["body"] = resp.status, resp.read().decode()
            except urllib.error.HTTPError as exc:
                seen["status"], seen["body"] = exc.code, exc.read().decode()

        monkeypatch.setattr(browser_auth, "_open_browser", fake_browser)
        monkeypatch.setattr(browser_auth, "exchange_auth_code", exchange)
        try:
            return browser_auth.authenticate_with_browser(
                access_type="oidc",
                auth_base_url="https://gw.example.com:8000",
                access_id="p-test",
                port=port,
            ), seen
        except Exception as exc:  # noqa: BLE001
            return exc, seen

    def test_auth_code_success(self, monkeypatch):
        from akeyless_agentcore_rta.browser_auth import BrowserAuthResult

        calls = []

        def exchange(base, code):
            calls.append((base, code))
            return BrowserAuthResult(token="t-short", expiration="1900000000000")

        result, seen = self._login(monkeypatch, "auth_code=code-1", exchange)
        assert calls == [("https://gw.example.com:8000", "code-1")]
        assert result.token == "t-short"
        assert seen["status"] == 200
        assert "Authentication succeeded" in seen["body"]

    def test_auth_code_rejected(self, monkeypatch):
        def exchange(base, code):
            raise RuntimeError("Auth code exchange failed (401)")

        result, seen = self._login(monkeypatch, "auth_code=bad", exchange)
        assert isinstance(result, RuntimeError)
        assert str(result) == "Auth code exchange failed (401)"
        assert seen["status"] == 400
        assert "Invalid auth code" in seen["body"]
