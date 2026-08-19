"""Low level HTTP transport / session client for the IceWarp Maintenance API."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import requests
from typing_extensions import Self

from . import xmlcodec
from .exceptions import (
    IceWarpAPIError,
    IceWarpAuthenticationError,
    IceWarpConnectionError,
)

DEFAULT_TIMEOUT = 30
API_PATH_SUFFIX = "icewarpapi"


def _normalize_base_url(base_url: str) -> str:
    """Ensure ``base_url`` contains the ``/icewarpapi`` mount path.

    IceWarp servers expose the Maintenance API under an ``/icewarpapi`` path
    (e.g. ``https://mail.example.com:32001/icewarpapi``). Users commonly pass
    just the host/port (``https://mail.example.com:32001``) - append the
    suffix automatically in that case so both forms work.
    """
    normalized = base_url.rstrip("/")
    if API_PATH_SUFFIX not in normalized.lower():
        normalized = f"{normalized}/{API_PATH_SUFFIX}"
    return normalized


class IceWarpClient:
    """Thin, generic client for the IceWarp Maintenance (admin) API.

    This class knows how to authenticate, keep track of the session id
    (``sid``) and send/parse the XML envelope used by *every* endpoint of the
    API. It intentionally does not hard-code knowledge about individual
    endpoints - use :meth:`call` to invoke any of the 174 documented
    operations directly, or use the higher level, generated, typed wrappers
    exposed by :class:`icewarp_api.api.IceWarpAPI` for a nicer developer
    experience.

    Example:
        >>> client = IceWarpClient("https://mail.example.com:32001/icewarpapi", verify_ssl=False)
        >>> client.login("admin@example.com", "hunter2")
        >>> client.call("GetDomainsInfoList")
        >>> client.logout()
    """

    def __init__(
        self,
        base_url: str,
        email: str | None = None,
        password: str | None = None,
        *,
        auth_type: str = "plain",
        timeout: float = DEFAULT_TIMEOUT,
        verify_ssl: bool = True,
        session: requests.Session | None = None,
        sid: str | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.email = email
        self.password = password
        self.auth_type = auth_type
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._http = session or requests.Session()
        self._sid = sid

    # -- session management -------------------------------------------------

    @property
    def sid(self) -> str | None:
        """The current session id, or ``None`` if not authenticated."""
        return self._sid

    @property
    def is_authenticated(self) -> bool:
        return self._sid is not None

    def login(
        self,
        email: str | None = None,
        password: str | None = None,
        *,
        auth_type: str | None = None,
        persistent_login: str | None = None,
        totp_code: str | None = None,
    ) -> str:
        """Authenticate with plain email/password and store the session id.

        Calls the ``/Authenticate`` endpoint. For other authentication flows
        (RSA challenge/digest, JWT, OAuth, SSO, gateway...) use
        :meth:`call` directly, e.g. ``client.call("GetAuthToken", ...)``.
        """
        email = email or self.email
        password = password if password is not None else self.password
        if not email or password is None:
            raise IceWarpAuthenticationError(
                "An 'email' and 'password' are required to authenticate."
            )

        params: dict[str, Any] = {
            "authtype": auth_type or self.auth_type,
            "email": email,
            "password": password,
            "persistentlogin": persistent_login,
            "totpcode": totp_code,
        }
        response = self._request("Authenticate", params, sid=None)
        sid = response.get("sid")
        if not sid:
            raise IceWarpAuthenticationError(
                "Authentication request succeeded but no session id (sid) was returned."
            )
        self._sid = sid
        self.email = email
        self.password = password
        return sid

    def use_session(self, sid: str) -> None:
        """Reuse an existing session id obtained elsewhere (skip login)."""
        self._sid = sid

    def logout(self) -> None:
        """Log out and invalidate the current session, if any."""
        if not self._sid:
            return
        try:
            self.call("Logout")
        finally:
            self._sid = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        if not self.is_authenticated and self.email and self.password is not None:
            self.login()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self.logout()
        finally:
            self.close()
        return False

    # -- generic calls --------------------------------------------------

    def call(self, command_name: str, **params: Any) -> Any:
        """Call any IceWarp Maintenance API endpoint by its command name.

        Args:
            command_name: The endpoint/command name, e.g. ``"GetDomainsInfoList"``
                (case-insensitive - matches the ``commandname`` field documented
                in the API).
            **params: The ``commandparams`` fields for this call. ``None``
                values are omitted so every optional parameter can be passed
                unconditionally.

        Returns:
            The parsed ``result`` value of the response: usually ``"0"`` for
            simple success, a ``dict``/``list`` of ``dict`` for list/info
            endpoints, or ``None`` when the endpoint returns no result body.
        """
        response = self._request(command_name, params, sid=self._sid)
        query = response.get("query")
        if isinstance(query, dict):
            return query.get("result")
        return None

    def call_raw(self, command_name: str, **params: Any) -> dict[str, Any]:
        """Like :meth:`call` but returns the full parsed response envelope."""
        return self._request(command_name, params, sid=self._sid)

    # -- internals --------------------------------------------------------

    def _request(
        self, command_name: str, params: dict[str, Any] | None, *, sid: str | None
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{command_name}"
        body = xmlcodec.build_request(command_name.lower(), params, sid=sid)

        try:
            http_response = self._http.post(
                url,
                data=body,
                headers={"Content-Type": "application/xml"},
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except requests.RequestException as exc:
            raise IceWarpConnectionError(
                f"Failed to reach IceWarp API at {url}: {exc}"
            ) from exc

        if http_response.status_code >= 400:
            raise IceWarpConnectionError(
                f"IceWarp API returned HTTP {http_response.status_code} for "
                f"{command_name}: {http_response.text[:500]!r}"
            )

        try:
            parsed = xmlcodec.parse_response(http_response.content)
        except ET.ParseError as exc:
            raise IceWarpAPIError(
                f"Could not parse XML response for {command_name}: {exc}",
                command_name=command_name,
                raw_response={"raw_text": http_response.text},
            ) from exc

        if parsed.get("type") == "error":
            query = parsed.get("query") if isinstance(parsed.get("query"), dict) else {}
            result = query.get("result") if isinstance(query, dict) else None
            detail = (
                result
                or (query.get("errortext") if isinstance(query, dict) else None)
                or parsed
            )
            raise IceWarpAPIError(
                f"IceWarp API returned an error response for {command_name}: {detail}",
                command_name=command_name,
                result=result,
                raw_response=parsed,
            )

        return parsed
