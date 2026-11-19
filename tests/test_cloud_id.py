from types import SimpleNamespace
from unittest.mock import MagicMock

import akeyless
import pytest

from akeyless_agentcore_rta import auth
from akeyless_agentcore_rta.config import config_from_env


class _FakeCloudId:
    calls: list = []

    def generate(self, *args, **kwargs):
        self.calls.append("aws")
        return "aws-id"

    def generateAzure(self, object_id=""):  # noqa: N802
        self.calls.append("azure")
        return "azure-id"

    def generateGcp(self, audience="akeyless.io"):  # noqa: N802
        self.calls.append(f"gcp:{audience}")
        return "gcp-id"


@pytest.fixture(autouse=True)
def fake_cloud_id(monkeypatch):
    _FakeCloudId.calls = []
    monkeypatch.setattr(auth, "CloudId", _FakeCloudId)


def _config(access_type, **overrides):
    return config_from_env(
        gateway_input_url="https://gw.example.com:8000",
        access_id="p-test",
        access_type=access_type,
        **overrides,
    )


@pytest.mark.parametrize(
    ("access_type", "overrides", "expected_id", "expected_call"),
    [
        ("aws_iam", {}, "aws-id", "aws"),
        ("azure_ad", {}, "azure-id", "azure"),
        ("gcp", {}, "gcp-id", "gcp:akeyless.io"),
        ("gcp", {"gcp_audience": "custom"}, "gcp-id", "gcp:custom"),
    ],
)
def test_cloud_id_generator_matches_provider(access_type, overrides, expected_id, expected_call):
    assert auth._get_cloud_id(_config(access_type, **overrides)) == expected_id
    assert _FakeCloudId.calls == [expected_call]


@pytest.mark.parametrize(
    ("access_type", "extra"),
    [("aws_iam", "aws"), ("azure_ad", "azure"), ("gcp", "gcp")],
)
def test_missing_provider_package_names_the_extra(monkeypatch, access_type, extra):
    class _Missing(_FakeCloudId):
        def generate(self, *args, **kwargs):
            raise ModuleNotFoundError("No module named 'boto3'")

        def generateAzure(self, object_id=""):  # noqa: N802
            raise ModuleNotFoundError("No module named 'azure'")

        def generateGcp(self, audience="akeyless.io"):  # noqa: N802
            raise ModuleNotFoundError("No module named 'google'")

    monkeypatch.setattr(auth, "CloudId", _Missing)
    with pytest.raises(ValueError, match=rf"akeyless-agentcore-rta\[{extra}\]"):
        auth._get_cloud_id(_config(access_type))


@pytest.mark.parametrize(
    ("access_type", "expected_audience"),
    [("gcp", "custom"), ("aws_iam", None), ("azure_ad", None)],
)
def test_gcp_audience_sent_only_for_gcp(access_type, expected_audience):
    api = MagicMock()
    api.auth.return_value = SimpleNamespace(token="t", expiration=None)
    auth.authenticate(api, _config(access_type, gcp_audience="custom"))
    body = api.auth.call_args[0][0]
    wire = akeyless.ApiClient().sanitize_for_serialization(body)
    assert wire.get("gcp-audience") == expected_audience


@pytest.mark.parametrize(
    ("access_type", "hint"),
    [("aws_iam", "AWS credentials"), ("azure_ad", "managed identity"), ("gcp", "service account")],
)
def test_empty_cloud_id_hint_is_provider_specific(monkeypatch, access_type, hint):
    class _Empty(_FakeCloudId):
        def generate(self, *args, **kwargs):
            return ""

        def generateAzure(self, object_id=""):  # noqa: N802
            return ""

        def generateGcp(self, audience="akeyless.io"):  # noqa: N802
            return ""

    monkeypatch.setattr(auth, "CloudId", _Empty)
    with pytest.raises(ValueError) as ei:
        auth._get_cloud_id(_config(access_type))
    assert hint in str(ei.value)
    if access_type != "aws_iam":
        assert "AWS" not in str(ei.value)
