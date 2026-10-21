"""Akeyless Agentic Runtime Authority (RTA/ARA) for AWS Bedrock AgentCore."""

from akeyless_agentcore_rta.client import AkeylessRtaClient, get_default_client
from akeyless_agentcore_rta.ara import AraSecretSummary, OAuthAuthorizationRequiredError

__all__ = [
    "AkeylessRtaClient",
    "AraSecretSummary",
    "OAuthAuthorizationRequiredError",
    "get_default_client",
]

__version__ = "0.1.0"
