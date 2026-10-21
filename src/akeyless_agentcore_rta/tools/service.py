"""Shared ARA tool logic for MCP (and future Strands / Gateway adapters)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from akeyless_agentcore_rta.ara import (
    OAuthAuthorizationRequiredError,
    format_oauth_required_message,
)
from akeyless_agentcore_rta.client import AkeylessRtaClient


@dataclass
class ToolResponse:
    ok: bool
    data: dict[str, Any]
    error: str | None = None

    def to_json(self) -> str:
        payload: dict[str, Any] = {"ok": self.ok, **self.data}
        if self.error:
            payload["error"] = self.error
        return json.dumps(payload)


class AraToolService:
    """Implements ARA operations exposed as AgentCore MCP tools."""

    def __init__(self, client: AkeylessRtaClient | None = None) -> None:
        self._client = client or AkeylessRtaClient()

    @property
    def client(self) -> AkeylessRtaClient:
        return self._client

    def list_secrets(self, path: str | None = None) -> ToolResponse:
        try:
            secrets = self._client.list_secrets(path=path)
            summaries = [s.to_dict() for s in secrets]
            return ToolResponse(
                ok=True,
                data={
                    "count": len(summaries),
                    "secrets": summaries,
                    "note": (
                        "Use query-db for database secrets or service-execute for "
                        "cloud/K8s/GitHub/custom-MCP secrets."
                        if summaries
                        else "No ARA secrets matched. Check Gateway ARA setup and role ara_allow_access."
                    ),
                },
            )
        except Exception as exc:
            return ToolResponse(ok=False, data={}, error=str(exc))

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
    ) -> ToolResponse:
        try:
            result = self._client.query_db(
                payload,
                secret_name=secret_name,
                agent_id=agent_id,
                original_user=original_user,
                original_prompt=original_prompt,
                auth_code=auth_code,
                state=state,
            )
            data = result.to_dict()
            data["note"] = (
                "Query executed via Akeyless Runtime Authority. Credentials were not exposed."
            )
            return ToolResponse(ok=True, data=data)
        except OAuthAuthorizationRequiredError as exc:
            return ToolResponse(
                ok=False,
                data={
                    "authorization_url": exc.authorization_url,
                    "state": exc.state,
                },
                error=format_oauth_required_message(exc),
            )
        except Exception as exc:
            return ToolResponse(ok=False, data={}, error=str(exc))

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
    ) -> ToolResponse:
        try:
            result = self._client.service_execute(
                payload,
                secret_name=secret_name,
                agent_id=agent_id,
                original_user=original_user,
                original_prompt=original_prompt,
                auth_code=auth_code,
                state=state,
            )
            data = result.to_dict()
            data["note"] = (
                "Action executed via Akeyless Runtime Authority. Credentials were not exposed."
            )
            return ToolResponse(ok=True, data=data)
        except OAuthAuthorizationRequiredError as exc:
            return ToolResponse(
                ok=False,
                data={
                    "authorization_url": exc.authorization_url,
                    "state": exc.state,
                },
                error=format_oauth_required_message(exc),
            )
        except Exception as exc:
            return ToolResponse(ok=False, data={}, error=str(exc))

    def list_sub_tools(
        self,
        *,
        secret_name: str | None = None,
        agent_id: str | None = None,
    ) -> ToolResponse:
        try:
            result = self._client.list_sub_tools(
                secret_name=secret_name,
                agent_id=agent_id,
            )
            data = result.to_dict()
            data["note"] = "Use service-execute with a payload that invokes the desired sub-tool."
            return ToolResponse(ok=True, data=data)
        except Exception as exc:
            return ToolResponse(ok=False, data={}, error=str(exc))
