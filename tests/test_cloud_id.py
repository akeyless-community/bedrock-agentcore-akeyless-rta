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
    cfg = config_from_env(
        gateway_input_url="https://gw.example.com:8000",
        access_id="p-test",
        access_type=access_type,
        **overrides,
    )
    assert auth._get_cloud_id(cfg) == expected_id
    assert _FakeCloudId.calls == [expected_call]
