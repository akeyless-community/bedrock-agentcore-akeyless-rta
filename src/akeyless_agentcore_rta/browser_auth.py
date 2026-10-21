"""SAML/OIDC browser login against the Akeyless Gateway (ARA product).

Mirrors claude-akeyless-connector ``browser-auth.ts``.
"""

from __future__ import annotations

import json
import platform
import subprocess
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Literal
from urllib.parse import parse_qs, urlparse

AUTH_TIMEOUT_SECONDS = 120
AccessBrowserType = Literal["saml", "oidc"]


@dataclass
class BrowserAuthResult:
    token: str
    creds: dict | None = None
    expiration: str | None = None


def build_login_path(access_type: AccessBrowserType) -> str:
    return "/api/saml-login" if access_type == "saml" else "/api/oidc-login"


def build_auth_url(
    auth_base_url: str,
    access_type: AccessBrowserType,
    access_id: str,
    redirect_uri: str,
) -> str:
    base = auth_base_url.rstrip("/")
    path = build_login_path(access_type)
    query = urllib.parse.urlencode(
        {
            "access_id": access_id,
            "redirect_uri": redirect_uri,
            "is_use_short_token": "true",
            "product": "ara",
        }
    )
    return f"{base}{path}?{query}"


def _parse_creds_param(creds: str) -> BrowserAuthResult:
    parsed = json.loads(creds)
    if not isinstance(parsed, dict):
        raise ValueError("Authentication response was not a JSON object")
    token = parsed.get("token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Authentication response did not include a token")
    creds_obj = parsed.get("creds")
    expiration = parsed.get("expiration")
    return BrowserAuthResult(
        token=token.strip(),
        creds=creds_obj if isinstance(creds_obj, dict) else None,
        expiration=str(expiration) if expiration is not None else None,
    )


def _open_browser(url: str) -> None:
    system = platform.system().lower()
    try:
        if system == "darwin":
            subprocess.run(["open", url], check=False)
            return
        if system == "windows":
            subprocess.run(["cmd", "/c", "start", "", url], check=False)
            return
        subprocess.run(["xdg-open", url], check=False)
    except OSError:
        webbrowser.open(url)


def authenticate_with_browser(
    *,
    access_type: AccessBrowserType,
    auth_base_url: str,
    access_id: str,
    port: int | None = None,
) -> BrowserAuthResult:
    if not access_id.strip():
        raise ValueError("Access ID is required for SAML/OIDC authentication")

    listen_port = port if port is not None else (11136 if access_type == "saml" else 11137)
    result_box: dict[str, BrowserAuthResult | BaseException | None] = {"value": None}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in ("/", ""):
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)
            error = (params.get("error") or [None])[0]
            if error:
                self._write_html(
                    400,
                    f"<p><strong>Authentication failed.</strong> {error}</p>",
                )
                result_box["value"] = RuntimeError(f"Authentication failed: {error}")
                done.set()
                return

            creds = (params.get("creds") or [None])[0]
            if not creds:
                self._write_html(400, "<p><strong>Authentication failed.</strong> Missing credentials in callback</p>")
                result_box["value"] = RuntimeError(
                    "Authentication callback did not include credentials"
                )
                done.set()
                return

            try:
                parsed_creds = _parse_creds_param(creds)
                self._write_html(
                    200,
                    "<p><strong>Authentication succeeded.</strong> You may close this tab and return to the agent.</p>",
                )
                result_box["value"] = parsed_creds
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self._write_html(
                    400,
                    f"<p><strong>Authentication failed.</strong> {message}</p>",
                )
                result_box["value"] = RuntimeError(message)
            done.set()

        def _write_html(self, status: int, body: str) -> None:
            content = f"<html><body>{body}</body></html>".encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    server = HTTPServer(("127.0.0.1", listen_port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    redirect_uri = f"http://127.0.0.1:{listen_port}"
    auth_url = build_auth_url(
        auth_base_url,
        access_type,
        access_id.strip(),
        redirect_uri,
    )

    print(
        f"[akeyless-agentcore-rta] Opening browser for {access_type.upper()} login...\n"
        f"[akeyless-agentcore-rta] {auth_url}",
        flush=True,
    )
    try:
        _open_browser(auth_url)
    except Exception:  # noqa: BLE001
        print(
            "[akeyless-agentcore-rta] Could not open a browser automatically. "
            "Open the URL above manually.",
            flush=True,
        )

    try:
        if not done.wait(timeout=AUTH_TIMEOUT_SECONDS):
            raise TimeoutError(
                f"{access_type} authentication timed out after {AUTH_TIMEOUT_SECONDS // 60} minutes"
            )
        value = result_box["value"]
        if isinstance(value, BaseException):
            raise value
        if not isinstance(value, BrowserAuthResult):
            raise RuntimeError("Authentication did not return a result")
        return value
    finally:
        server.shutdown()
        server.server_close()
