"""Authenticate to Akeyless using cloud identity, browser OIDC/SAML, or other methods."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import akeyless
from akeyless_cloud_id import CloudId

from akeyless_agentcore_rta.browser_auth import authenticate_with_browser
from akeyless_agentcore_rta.config import AkeylessRtaConfig

ACCESS_KEY_DEFAULT_TTL_SECONDS = 14 * 60
ENV_TOKEN_TTL_SECONDS = 50 * 60


@dataclass
class AuthSession:
    token: str
    expires_at: float
    creds: dict[str, Any] | None = field(default=None)


def _expiry_from_auth_output(auth_out: akeyless.AuthOutput, margin_seconds: float) -> float:
    now = time.monotonic()
    expiration = getattr(auth_out, "expiration", None)
    if not expiration:
        return now + ACCESS_KEY_DEFAULT_TTL_SECONDS - margin_seconds

    raw = str(expiration).strip()
    if not raw:
        return now + ACCESS_KEY_DEFAULT_TTL_SECONDS - margin_seconds

    try:
        as_num = float(raw)
        if as_num > 1e12:
            return (as_num / 1000.0) - time.time() + now - margin_seconds
    except ValueError:
        pass

    try:
        as_date = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if as_date.tzinfo is None:
            as_date = as_date.replace(tzinfo=timezone.utc)
        return as_date.timestamp() - time.time() + now - margin_seconds
    except ValueError:
        pass

    return now + ACCESS_KEY_DEFAULT_TTL_SECONDS - margin_seconds


def _expiry_from_browser(
    expiration: str | None,
    margin_seconds: float,
) -> float:
    now = time.monotonic()
    if not expiration or not str(expiration).strip():
        return now + ACCESS_KEY_DEFAULT_TTL_SECONDS - margin_seconds
    # Reuse AuthOutput-style parsing via a tiny shim
    class _Shim:
        def __init__(self, expiration: str) -> None:
            self.expiration = expiration

    return _expiry_from_auth_output(_Shim(str(expiration)), margin_seconds)  # type: ignore[arg-type]


def _get_cloud_id(config: AkeylessRtaConfig) -> str:
    if config.cloud_id and config.cloud_id.strip():
        return config.cloud_id.strip()

    provider = config.cloud_provider or config.access_type
    if provider not in ("aws_iam", "azure_ad", "gcp"):
        raise ValueError(f"Cannot generate cloud ID for access type {provider}")

    cloud_id = CloudId().generate()
    if not cloud_id or not str(cloud_id).strip():
        raise ValueError(
            f"akeyless-cloud-id returned an empty cloud ID for provider {provider!r}. "
            "On AgentCore Runtime, ensure the execution role has ambient AWS credentials "
            "or pass cloud_id explicitly."
        )
    return str(cloud_id).strip()


def create_v2_api(sdk_gateway_url: str) -> akeyless.V2Api:
    """Create V2Api pointed at the customer Gateway SDK base (…/api/v2)."""
    host = sdk_gateway_url.rstrip("/")
    configuration = akeyless.Configuration(host=host)
    return akeyless.V2Api(akeyless.ApiClient(configuration))


def authenticate(api: akeyless.V2Api, config: AkeylessRtaConfig) -> AuthSession:
    now = time.monotonic()

    if config.token and config.token.strip():
        return AuthSession(
            token=config.token.strip(),
            expires_at=now + ENV_TOKEN_TTL_SECONDS,
        )

    access_type = config.access_type

    if access_type in ("saml", "oidc"):
        browser = authenticate_with_browser(
            access_type=access_type,  # type: ignore[arg-type]
            auth_base_url=config.ara_gateway_url,
            access_id=config.access_id or "",
        )
        return AuthSession(
            token=browser.token,
            expires_at=_expiry_from_browser(
                browser.expiration,
                config.token_expiry_margin_seconds,
            ),
            creds=browser.creds,
        )

    if access_type in ("access_key", "api_key"):
        body = akeyless.Auth(
            access_id=config.access_id,
            access_type=access_type,
            access_key=config.access_key,
        )
    elif access_type == "universal_identity":
        body = akeyless.Auth(
            access_type="universal_identity",
            uid_token=config.uid_token,
        )
    elif access_type == "jwt":
        body = akeyless.Auth(
            access_id=config.access_id,
            access_type="jwt",
            jwt=config.jwt,
        )
    elif access_type in ("aws_iam", "azure_ad", "gcp"):
        body = akeyless.Auth(
            access_id=config.access_id,
            access_type=access_type,
            cloud_id=_get_cloud_id(config),
        )
    else:
        raise ValueError(f"Unsupported access type: {access_type}")

    auth_out = api.auth(body)
    token = getattr(auth_out, "token", None)
    if not token or not str(token).strip():
        raise ValueError("Akeyless authentication did not return a token")

    return AuthSession(
        token=str(token).strip(),
        expires_at=_expiry_from_auth_output(auth_out, config.token_expiry_margin_seconds),
    )


def build_gateway_auth_header(session: AuthSession | str) -> dict[str, str]:
    """Build Authorization header for Gateway ARA config-port calls.

    Prefer base64(JSON creds) when browser login returned ``creds`` (SAML/OIDC),
    otherwise Bearer token — same as Claude/Cursor ARA connectors.
    """
    if isinstance(session, str):
        trimmed = session.strip()
        if not trimmed:
            raise ValueError("Unable to build gateway authorization header: empty token")
        return {"Authorization": f"Bearer {trimmed}"}

    if session.creds:
        encoded = base64.b64encode(
            json.dumps(session.creds, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        return {"Authorization": f"Bearer {encoded}"}

    trimmed = session.token.strip()
    if not trimmed:
        raise ValueError("Unable to build gateway authorization header: empty token")
    return {"Authorization": f"Bearer {trimmed}"}
