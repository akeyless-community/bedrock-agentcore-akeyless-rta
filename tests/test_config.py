import pytest

from akeyless_agentcore_rta.config import (
    config_from_env,
    is_public_saas_gateway,
    parse_ara_gateway_url,
    parse_sdk_gateway_url,
    validate_config,
)


class TestGatewayUrlParsers:
    def test_parse_sdk_adds_api_v2(self):
        assert parse_sdk_gateway_url("https://gw.example.com:8000") == (
            "https://gw.example.com:8000/api/v2"
        )

    def test_parse_sdk_keeps_api_v2(self):
        assert parse_sdk_gateway_url("https://gw.example.com:8000/api/v2") == (
            "https://gw.example.com:8000/api/v2"
        )

    def test_parse_ara_strips_api_v2(self):
        assert parse_ara_gateway_url("https://gw.example.com:8000/api/v2") == (
            "https://gw.example.com:8000"
        )

    def test_parse_ara_keeps_base(self):
        assert parse_ara_gateway_url("https://gw.example.com:8000") == (
            "https://gw.example.com:8000"
        )


class TestPublicSaasRejection:
    def test_detects_public_host(self):
        assert is_public_saas_gateway("https://api.akeyless.io")
        assert is_public_saas_gateway("https://api.akeyless.io/api/v2")

    def test_allows_customer_gw(self):
        assert not is_public_saas_gateway("https://gw.example.com:8000")
        assert not is_public_saas_gateway("https://gw.example.com:8000/api/v2")


class TestValidateConfig:
    def test_requires_gateway(self):
        cfg = config_from_env(access_id="p-test", access_type="aws_iam")
        with pytest.raises(ValueError, match="AKEYLESS_GATEWAY_URL"):
            validate_config(cfg)

    def test_rejects_public_saas(self):
        cfg = config_from_env(
            gateway_input_url="https://api.akeyless.io",
            access_id="p-test",
            access_type="aws_iam",
        )
        with pytest.raises(ValueError, match="customer or self-hosted Gateway"):
            validate_config(cfg)

    def test_rejects_public_saas_with_api_v2(self):
        cfg = config_from_env(
            gateway_input_url="https://api.akeyless.io/api/v2",
            access_id="p-test",
            access_type="aws_iam",
        )
        with pytest.raises(ValueError, match="customer or self-hosted Gateway"):
            validate_config(cfg)

    def test_accepts_customer_gateway(self):
        cfg = config_from_env(
            gateway_input_url="https://gw.example.com:8000",
            access_id="p-test",
            access_type="aws_iam",
        )
        validate_config(cfg)
        assert cfg.gateway_url == "https://gw.example.com:8000/api/v2"
        assert cfg.ara_gateway_url == "https://gw.example.com:8000"
