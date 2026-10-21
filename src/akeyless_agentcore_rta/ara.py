"""ARA list-items mapping and producer-type helpers.

Ported from claude-akeyless-connector ``ara.ts`` to match gateway ListARASecrets
behavior and MCP tool routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ARA_DB_PRODUCER_TYPES = frozenset(
    {
        "mysql",
        "postgres",
        "mssql",
        "oracle",
        "snowflake",
        "hana",
        "redshift",
        "mongodb",
        "redis",
        "cassandra",
    }
)

ARA_SERVICE_PRODUCER_TYPES = frozenset(
    {
        "aws",
        "gcp",
        "azure",
        "k8s",
        "eks",
        "gke",
        "github",
    }
)

# Synthetic label for static-secret custom MCP configs (Go: CustomMCPTargetType).
CUSTOM_MCP_TARGET_TYPE = "custom-mcp"

ARA_LIST_ITEM_TYPES = ["dynamic-secret", "rotated-secret", "static-secret"]

SecretTypeLabel = Literal["dynamic-secret", "rotated-secret", "static-secret"]


def is_ara_db_producer_type(producer_type: str) -> bool:
    return producer_type.lower() in ARA_DB_PRODUCER_TYPES


def is_ara_service_producer_type(producer_type: str) -> bool:
    normalized = producer_type.lower()
    return normalized in ARA_SERVICE_PRODUCER_TYPES or normalized == CUSTOM_MCP_TARGET_TYPE


def is_ara_supported_producer_type(producer_type: str) -> bool:
    normalized = producer_type.lower()
    return normalized in ARA_DB_PRODUCER_TYPES or normalized in ARA_SERVICE_PRODUCER_TYPES


def normalize_item_type(raw: str | None) -> str:
    return (raw or "").strip().lower().replace("_", "-")


@dataclass(frozen=True)
class AraSecretSummary:
    name: str
    secret_type: SecretTypeLabel
    target_type: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "secret_type": self.secret_type,
        }
        if self.target_type:
            out["target_type"] = self.target_type
        if self.description:
            out["description"] = self.description
        return out


def build_ara_list_items_body(
    token: str,
    *,
    path: str | None = None,
    ara_only: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "token": token,
        "filter": "",
        "type": list(ARA_LIST_ITEM_TYPES),
        "ara-only": ara_only,
        "advanced-filter": "",
    }
    trimmed = (path or "").strip()
    if trimmed:
        body["path"] = trimmed
    return body


def _item_get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _extract_dynamic_producer_type(item: Any) -> str | None:
    general = _item_get(item, "item_general_info") or {}
    if not isinstance(general, dict):
        general = {
            "dynamic_secret_producer_details": getattr(
                general, "dynamic_secret_producer_details", None
            )
        }
    details = general.get("dynamic_secret_producer_details") if isinstance(general, dict) else None
    if details is None:
        details = _item_get(item, "dynamic_secret_producer_details")
    if details is None:
        return None
    if isinstance(details, dict):
        producer = details.get("producer_type")
    else:
        producer = getattr(details, "producer_type", None)
    if producer is None:
        return None
    trimmed = str(producer).strip().lower()
    return trimmed or None


def _extract_rotated_target_type(item: Any) -> str | None:
    assoc = _item_get(item, "item_targets_assoc") or []
    if not assoc:
        return None
    first = assoc[0]
    if isinstance(first, dict):
        target = first.get("target_type")
    else:
        target = getattr(first, "target_type", None)
    if target is None:
        return None
    trimmed = str(target).strip().lower()
    return trimmed or None


def map_ara_secrets(items: list[Any]) -> list[AraSecretSummary]:
    results: list[AraSecretSummary] = []

    for item in items:
        name = _item_get(item, "item_name")
        if not name or not str(name).strip():
            continue
        name = str(name).strip()

        perms = _item_get(item, "client_permissions") or []
        if "ara_allow_access" not in perms:
            continue

        item_type = normalize_item_type(str(_item_get(item, "item_type") or ""))
        metadata = _item_get(item, "item_metadata")
        description = str(metadata).strip() if metadata else None
        if description == "":
            description = None

        if item_type == "dynamic-secret":
            target_type = _extract_dynamic_producer_type(item)
            if not target_type or not is_ara_supported_producer_type(target_type):
                continue
            results.append(
                AraSecretSummary(
                    name=name,
                    secret_type="dynamic-secret",
                    target_type=target_type,
                    description=description,
                )
            )
            continue

        if item_type == "rotated-secret":
            target_type = _extract_rotated_target_type(item)
            if target_type and not is_ara_supported_producer_type(target_type):
                continue
            results.append(
                AraSecretSummary(
                    name=name,
                    secret_type="rotated-secret",
                    target_type=target_type,
                    description=description,
                )
            )
            continue

        if item_type == "static-secret":
            results.append(
                AraSecretSummary(
                    name=name,
                    secret_type="static-secret",
                    target_type=CUSTOM_MCP_TARGET_TYPE,
                    description=description,
                )
            )

    results.sort(key=lambda s: s.name)
    return results


class OAuthAuthorizationRequiredError(Exception):
    """Gateway returned 401 with an OAuth authorization_url + state challenge."""

    def __init__(self, authorization_url: str, state: str) -> None:
        self.authorization_url = authorization_url
        self.state = state
        super().__init__(f"OAuth authorization required: {authorization_url}")


def format_oauth_required_message(error: OAuthAuthorizationRequiredError) -> str:
    return (
        "This secret requires OAuth authorization. "
        "Please open the following URL in your browser to authorize, "
        "then call this tool again with the auth-code and state parameters.\n\n"
        f"Authorization URL: {error.authorization_url}\nState: {error.state}"
    )
