from akeyless_agentcore_rta.browser_auth import build_auth_url
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
