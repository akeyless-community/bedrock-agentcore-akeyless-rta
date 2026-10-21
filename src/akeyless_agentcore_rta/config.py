"""Configuration from environment variables and explicit overrides."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

AccessType = Literal[
    "access_key",
    "api_key",
    "aws_iam",
    "azure_ad",
    "gcp",
    "universal_identity",
    "jwt",
    "saml",
    "oidc",
]
CloudProvider = Literal["aws_iam", "azure_ad", "gcp"]

API_V2_SUFFIX = "/api/v2"
DEFAULT_AGENT_ID = "bedrock-agentcore"
DEFAULT_MCP_ID = "akeyless-agentcore-rta"
DEFAULT_TOKEN_EXPIRY_MARGIN_SECONDS = 60
PUBLIC_SAAS_HOST = "api.akeyless.io"


def _read_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _parse_positive_float(raw: str | None, fallback: float) -> float:
    if raw is None:
        return fallback
    try:
        parsed = float(raw)
    except ValueError:
        return fallback
    return parsed if parsed >= 0 else fallback


def _parse_access_type(raw: str | None) -> AccessType:
    value = (raw or "aws_iam").lower()
    if value == "api_key":
        return "access_key"
    allowed: tuple[AccessType, ...] = (
        "access_key",
        "api_key",
        "aws_iam",
        "azure_ad",
        "gcp",
        "universal_identity",
        "jwt",
        "saml",
        "oidc",
    )
    if value not in allowed:
        raise ValueError(
            f'Unsupported AKEYLESS_ACCESS_TYPE "{raw}". '
            "Expected access_key, api_key, aws_iam, azure_ad, gcp, universal_identity, jwt, saml, or oidc."
        )
    return value  # type: ignore[return-type]


def _cloud_provider_for_access_type(access_type: AccessType) -> CloudProvider | None:
    if access_type in ("aws_iam", "azure_ad", "gcp"):
        return access_type
    return None


def _normalize_gateway_input(input_url: str) -> str:
    base = input_url.strip().rstrip("/")
    if not base:
        raise ValueError("Gateway URL is required")
    return base


def parse_ara_gateway_url(input_url: str) -> str:
    """Config-port base for ARA execute (`/config/target_query`).

    Accepts ``https://gw:8000`` or ``https://gw:8000/api/v2`` and returns
    the base without ``/api/v2``.
    """
    base = _normalize_gateway_input(input_url)
    if base.lower().endswith(API_V2_SUFFIX):
        return base[: -len(API_V2_SUFFIX)]
    return base


def parse_sdk_gateway_url(input_url: str) -> str:
    """SDK API base for auth and list-items (always ends with ``/api/v2``)."""
    base = _normalize_gateway_input(input_url)
    if base.lower().endswith(API_V2_SUFFIX):
        return base
    return f"{base}{API_V2_SUFFIX}"


def is_public_saas_gateway(url: str) -> bool:
    """Return True if URL host is the public Akeyless SaaS API (no ARA)."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""
    if not host and PUBLIC_SAAS_HOST in url.lower():
        return True
    return host == PUBLIC_SAAS_HOST or host.endswith("." + PUBLIC_SAAS_HOST)


@dataclass
class AkeylessRtaConfig:
    gateway_url: str = ""
    ara_gateway_url: str = ""
    access_type: AccessType = "aws_iam"
    access_id: str | None = None
    access_key: str | None = None
    uid_token: str | None = None
    jwt: str | None = None
    token: str | None = None
    cloud_id: str | None = None
    cloud_provider: CloudProvider | None = None
    agent_id: str = DEFAULT_AGENT_ID
    mcp_id: str = DEFAULT_MCP_ID
    default_secret_name: str | None = None
    token_expiry_margin_seconds: float = DEFAULT_TOKEN_EXPIRY_MARGIN_SECONDS


def config_from_env(**overrides: object) -> AkeylessRtaConfig:
    access_type = overrides.get("access_type") or _parse_access_type(
        _read_env("AKEYLESS_ACCESS_TYPE")
    )

    cloud_provider = overrides.get("cloud_provider")
    if cloud_provider is None:
        cloud_provider = _cloud_provider_for_access_type(access_type)  # type: ignore[arg-type]

    ara_override = overrides.get("ara_gateway_url") or _read_env("AKEYLESS_ARA_GATEWAY_URL")
    sdk_override = overrides.get("gateway_url") or _read_env("AKEYLESS_API_URL")
    raw_gateway = overrides.get("gateway_input_url") or _read_env("AKEYLESS_GATEWAY_URL")

    gateway_url = ""
    ara_gateway_url = ""
    if isinstance(ara_override, str) and ara_override.strip():
        ara_gateway_url = parse_ara_gateway_url(ara_override)
    if isinstance(sdk_override, str) and sdk_override.strip():
        gateway_url = parse_sdk_gateway_url(sdk_override)
    elif isinstance(raw_gateway, str) and raw_gateway.strip():
        gateway_url = parse_sdk_gateway_url(raw_gateway)
        if not ara_gateway_url:
            ara_gateway_url = parse_ara_gateway_url(raw_gateway)

    if gateway_url and not ara_gateway_url:
        ara_gateway_url = parse_ara_gateway_url(gateway_url)

    mcp_id = overrides.get("mcp_id") or _read_env("AKEYLESS_MCP_ID") or DEFAULT_MCP_ID
    if mcp_id == "auto":
        mcp_id = str(uuid.uuid4())

    return AkeylessRtaConfig(
        gateway_url=str(gateway_url),
        ara_gateway_url=str(ara_gateway_url),
        access_type=access_type,  # type: ignore[arg-type]
        access_id=overrides.get("access_id") or _read_env("AKEYLESS_ACCESS_ID"),  # type: ignore[arg-type]
        access_key=(
            overrides.get("access_key")  # type: ignore[assignment]
            or _read_env("AKEYLESS_ACCESS_KEY")
            or _read_env("AKEYLESS_API_KEY")
        ),
        uid_token=(
            overrides.get("uid_token")  # type: ignore[assignment]
            or _read_env("AKEYLESS_UID_TOKEN")
            or _read_env("AKEYLESS_UNIVERSAL_IDENTITY_TOKEN")
        ),
        jwt=overrides.get("jwt") or _read_env("AKEYLESS_JWT"),  # type: ignore[arg-type]
        token=overrides.get("token") or _read_env("AKEYLESS_TOKEN"),  # type: ignore[arg-type]
        cloud_id=overrides.get("cloud_id") or _read_env("AKEYLESS_CLOUD_ID"),  # type: ignore[arg-type]
        cloud_provider=cloud_provider,  # type: ignore[arg-type]
        agent_id=str(
            overrides.get("agent_id") or _read_env("AKEYLESS_AGENT_ID") or DEFAULT_AGENT_ID
        ),
        mcp_id=str(mcp_id),
        default_secret_name=(
            overrides.get("default_secret_name")  # type: ignore[assignment]
            or _read_env("AKEYLESS_DEFAULT_SECRET_NAME")
        ),
        token_expiry_margin_seconds=float(
            overrides.get("token_expiry_margin_seconds")
            or _parse_positive_float(
                _read_env("AKEYLESS_TOKEN_EXPIRY_MARGIN_SECONDS"),
                DEFAULT_TOKEN_EXPIRY_MARGIN_SECONDS,
            )
        ),
    )


def validate_config(config: AkeylessRtaConfig) -> None:
    if not config.gateway_url.strip() or not config.ara_gateway_url.strip():
        raise ValueError(
            "AKEYLESS_GATEWAY_URL is required and must point to your Akeyless Gateway "
            "with Agentic Runtime Authority (ARA) enabled "
            "(e.g. https://gw.example.com:8000 or https://gw.example.com:8000/api/v2). "
            "The public SaaS API (api.akeyless.io) does not support ARA."
        )

    if is_public_saas_gateway(config.gateway_url) or is_public_saas_gateway(
        config.ara_gateway_url
    ):
        raise ValueError(
            "Akeyless RTA/ARA requires a customer or self-hosted Gateway with ARA enabled. "
            f"Do not use the public SaaS API ({PUBLIC_SAAS_HOST}). "
            "Set AKEYLESS_GATEWAY_URL to your Gateway address."
        )

    if config.token and config.token.strip():
        return

    if config.access_type in ("access_key", "api_key"):
        if not config.access_id or not config.access_key:
            raise ValueError(
                "access_id and access_key are required for access_key/api_key authentication "
                "(or set token / AKEYLESS_TOKEN)"
            )
        return

    if config.access_type == "universal_identity":
        if not config.uid_token:
            raise ValueError(
                "uid_token is required for universal_identity authentication "
                "(or set token / AKEYLESS_TOKEN)"
            )
        return

    if config.access_type == "jwt":
        if not config.access_id or not config.jwt:
            raise ValueError(
                "access_id and jwt are required for jwt authentication "
                "(or set token / AKEYLESS_TOKEN)"
            )
        return

    if config.access_type in ("aws_iam", "azure_ad", "gcp", "saml", "oidc"):
        if not config.access_id:
            raise ValueError(
                f"{config.access_type} authentication requires access_id "
                "(or set token / AKEYLESS_TOKEN)"
            )
        return

    raise ValueError(f"Unsupported access type: {config.access_type}")
