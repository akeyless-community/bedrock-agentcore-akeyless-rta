"""HTTP helpers for Akeyless Gateway ARA config-port endpoints."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from akeyless_agentcore_rta.ara import OAuthAuthorizationRequiredError


@dataclass
class TargetQueryResult:
    target_type: str | None = None
    results: list[dict[str, Any]] | None = None
    raw: Any = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.target_type is not None:
            out["target_type"] = self.target_type
        if self.results is not None:
            out["results"] = self.results
        if self.raw is not None and "raw" not in out:
            # Prefer structured fields; include raw only when useful for debugging
            # non-object responses. Callers typically serialize target_type/results.
            if not out:
                out["raw"] = self.raw
        return out if out else {"raw": self.raw}


@dataclass
class ListSubToolsTool:
    name: str
    description: str | None = None
    parameters: Any = None


@dataclass
class ListSubToolsResult:
    target_type: str | None = None
    tools: list[ListSubToolsTool] | None = None
    raw: Any = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.target_type is not None:
            out["target_type"] = self.target_type
        if self.tools is not None:
            out["tools"] = [
                {
                    "name": t.name,
                    **({"description": t.description} if t.description else {}),
                    **({"parameters": t.parameters} if t.parameters is not None else {}),
                }
                for t in self.tools
            ]
        if not out and self.raw is not None:
            out["raw"] = self.raw
        return out


def _is_oauth_required_body(parsed: Any) -> bool:
    if not isinstance(parsed, dict):
        return False
    url = parsed.get("authorization_url")
    state = parsed.get("state")
    return isinstance(url, str) and bool(url) and isinstance(state, str) and bool(state)


def post_ara_json(
    gateway_url: str,
    path: str,
    auth_header: dict[str, str],
    body: dict[str, Any],
    failure_label: str,
    *,
    opener: Any | None = None,
) -> Any:
    """POST JSON to an ARA gateway endpoint and return the parsed response.

    ``opener`` is an optional callable ``(Request) -> http.client.HTTPResponse``
    used by tests to stub network I/O.
    """
    base = gateway_url.rstrip("/")
    url = f"{base}{path}"
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **auth_header,
    }
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")

    do_open = opener or urllib.request.urlopen
    try:
        with do_open(request, timeout=120) as response:
            text = response.read().decode("utf-8")
            status = getattr(response, "status", None) or response.getcode()
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        status = exc.code
        parsed: Any
        try:
            parsed = json.loads(text) if text else {}
        except json.JSONDecodeError:
            parsed = {"raw": text}
        if status == 401 and _is_oauth_required_body(parsed):
            raise OAuthAuthorizationRequiredError(
                str(parsed["authorization_url"]),
                str(parsed["state"]),
            ) from exc
        message = (
            parsed.get("error")
            if isinstance(parsed, dict) and isinstance(parsed.get("error"), str)
            else (text or f"Gateway {failure_label} failed ({status})")
        )
        raise RuntimeError(message) from exc

    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        parsed = {"raw": text}

    if status is not None and int(status) >= 400:
        if status == 401 and _is_oauth_required_body(parsed):
            raise OAuthAuthorizationRequiredError(
                str(parsed["authorization_url"]),
                str(parsed["state"]),
            )
        message = (
            parsed.get("error")
            if isinstance(parsed, dict) and isinstance(parsed.get("error"), str)
            else (text or f"Gateway {failure_label} failed ({status})")
        )
        raise RuntimeError(message)

    return parsed


def post_target_query(
    gateway_url: str,
    auth_header: dict[str, str],
    body: dict[str, Any],
    *,
    opener: Any | None = None,
) -> TargetQueryResult:
    parsed = post_ara_json(
        gateway_url,
        "/config/target_query",
        auth_header,
        body,
        "target query",
        opener=opener,
    )
    if isinstance(parsed, dict):
        results = parsed.get("results")
        if results is not None and not isinstance(results, list):
            results = None
        return TargetQueryResult(
            target_type=parsed.get("target_type")
            if isinstance(parsed.get("target_type"), str)
            else None,
            results=results,  # type: ignore[arg-type]
            raw=parsed,
        )
    return TargetQueryResult(raw=parsed)


def post_list_sub_tools(
    gateway_url: str,
    auth_header: dict[str, str],
    body: dict[str, Any],
    *,
    opener: Any | None = None,
) -> ListSubToolsResult:
    parsed = post_ara_json(
        gateway_url,
        "/config/list_sub_tools",
        auth_header,
        body,
        "list sub-tools",
        opener=opener,
    )
    if isinstance(parsed, dict):
        tools_raw = parsed.get("tools")
        tools: list[ListSubToolsTool] | None = None
        if isinstance(tools_raw, list):
            tools = []
            for entry in tools_raw:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    tools.append(
                        ListSubToolsTool(
                            name=entry["name"],
                            description=entry.get("description")
                            if isinstance(entry.get("description"), str)
                            else None,
                            parameters=entry.get("parameters"),
                        )
                    )
        return ListSubToolsResult(
            target_type=parsed.get("target_type")
            if isinstance(parsed.get("target_type"), str)
            else None,
            tools=tools,
            raw=parsed,
        )
    return ListSubToolsResult(raw=parsed)
