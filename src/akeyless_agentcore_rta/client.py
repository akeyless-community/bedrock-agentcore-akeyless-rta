"""Akeyless RTA/ARA client for Bedrock AgentCore agents."""

from __future__ import annotations

import time
from typing import Any, Callable

import akeyless

from akeyless_agentcore_rta.ara import (
    AraSecretSummary,
    is_ara_db_producer_type,
    is_ara_service_producer_type,
    map_ara_secrets,
)
from akeyless_agentcore_rta.auth import (
    AuthSession,
    authenticate,
    build_gateway_auth_header,
    create_v2_api,
)
from akeyless_agentcore_rta.config import AkeylessRtaConfig, config_from_env, validate_config
from akeyless_agentcore_rta.http_ara import (
    ListSubToolsResult,
    TargetQueryResult,
    post_list_sub_tools,
    post_target_query,
)

HttpOpener = Callable[..., Any]


class AkeylessRtaClient:
    """Secretless ARA client: list eligible secrets and run query/execute via Gateway."""

    def __init__(
        self,
        *,
        _http_opener: HttpOpener | None = None,
        _api: akeyless.V2Api | None = None,
        **config_overrides: Any,
    ) -> None:
        self._config = config_from_env(**config_overrides)
        validate_config(self._config)
        self._api = _api or create_v2_api(self._config.gateway_url)
        self._session: AuthSession | None = None
        self._http_opener = _http_opener

    @classmethod
    def from_env(cls, **overrides: Any) -> AkeylessRtaClient:
        return cls(**overrides)

    @property
    def config(self) -> AkeylessRtaConfig:
        return self._config

    def _get_session(self) -> AuthSession:
        now = time.monotonic()
        if self._session and now < self._session.expires_at:
            return self._session
        self._session = authenticate(self._api, self._config)
        return self._session

    def _get_token(self) -> str:
        return self._get_session().token

    def _gateway_auth_header(self) -> dict[str, str]:
        return build_gateway_auth_header(self._get_session())

    def list_secrets(self, path: str | None = None) -> list[AraSecretSummary]:
        """List ARA-enabled secrets (metadata only — never values)."""
        token = self._get_token()
        kwargs: dict[str, Any] = {
            "token": token,
            "filter": "",
            "type": ["dynamic-secret", "rotated-secret", "static-secret"],
            "ara_only": True,
            "advanced_filter": "",
        }
        trimmed = (path or "").strip()
        if trimmed:
            kwargs["path"] = trimmed

        result = self._api.list_items(akeyless.ListItems(**kwargs))
        items = getattr(result, "items", None) or []
        return map_ara_secrets(list(items))

    def _resolve_secret_name(self, secret_name: str | None) -> str:
        name = (secret_name or self._config.default_secret_name or "").strip()
        if not name:
            raise ValueError(
                "secret_name is required (or configure AKEYLESS_DEFAULT_SECRET_NAME)"
            )
        return name

    def _find_listed_secret(self, secret_name: str) -> AraSecretSummary | None:
        try:
            secrets = self.list_secrets()
        except Exception:
            return None
        return next((s for s in secrets if s.name == secret_name), None)

    def query_db(
        self,
        payload: str,
        *,
        secret_name: str | None = None,
        agent_id: str | None = None,
        original_user: str | None = None,
        original_prompt: str | None = None,
        auth_code: str | None = None,
        state: str | None = None,
    ) -> TargetQueryResult:
        """Run a database query via Gateway ARA (credentials never returned)."""
        resolved = self._resolve_secret_name(secret_name)
        listed = self._find_listed_secret(resolved)
        if listed and listed.target_type and not is_ara_db_producer_type(listed.target_type):
            raise ValueError(
                f'Secret "{resolved}" is not a database secret. Use service_execute instead.'
            )
        return self._execute_target_query(
            secret_name=resolved,
            payload=payload,
            agent_id=agent_id,
            original_user=original_user,
            original_prompt=original_prompt,
            auth_code=auth_code,
            state=state,
        )

    def service_execute(
        self,
        payload: str,
        *,
        secret_name: str | None = None,
        agent_id: str | None = None,
        original_user: str | None = None,
        original_prompt: str | None = None,
        auth_code: str | None = None,
        state: str | None = None,
    ) -> TargetQueryResult:
        """Run a cloud/K8s/GitHub/custom-MCP action via Gateway ARA."""
        resolved = self._resolve_secret_name(secret_name)
        listed = self._find_listed_secret(resolved)
        if listed and listed.target_type and not is_ara_service_producer_type(listed.target_type):
            raise ValueError(
                f'Secret "{resolved}" is not a service secret. Use query_db instead.'
            )
        return self._execute_target_query(
            secret_name=resolved,
            payload=payload,
            agent_id=agent_id,
            original_user=original_user,
            original_prompt=original_prompt,
            auth_code=auth_code,
            state=state,
        )

    def _execute_target_query(
        self,
        *,
        secret_name: str,
        payload: str,
        agent_id: str | None,
        original_user: str | None,
        original_prompt: str | None,
        auth_code: str | None,
        state: str | None,
    ) -> TargetQueryResult:
        body: dict[str, Any] = {
            "secret_name": secret_name,
            "payload": payload,
            "agent_id": agent_id or self._config.agent_id,
            "mcp_id": self._config.mcp_id,
        }
        if auth_code:
            body["auth_code"] = auth_code
        if state:
            body["state"] = state
        if original_user:
            body["original_user"] = original_user
        if original_prompt:
            body["original_prompt"] = original_prompt

        return post_target_query(
            self._config.ara_gateway_url,
            self._gateway_auth_header(),
            body,
            opener=self._http_opener,
        )

    def list_sub_tools(
        self,
        *,
        secret_name: str | None = None,
        agent_id: str | None = None,
    ) -> ListSubToolsResult:
        """Discover sub-tools for a service secret (optional before service_execute)."""
        resolved = self._resolve_secret_name(secret_name)
        body = {
            "secret_name": resolved,
            "agent_id": agent_id or self._config.agent_id,
            "mcp_id": self._config.mcp_id,
        }
        return post_list_sub_tools(
            self._config.ara_gateway_url,
            self._gateway_auth_header(),
            body,
            opener=self._http_opener,
        )


_default_client: AkeylessRtaClient | None = None


def get_default_client(**overrides: Any) -> AkeylessRtaClient:
    global _default_client
    if overrides or _default_client is None:
        _default_client = AkeylessRtaClient(**overrides)
    return _default_client
