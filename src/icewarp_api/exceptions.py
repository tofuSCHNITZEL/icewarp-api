"""Exceptions raised by the icewarp_api package."""

from __future__ import annotations

from typing import Any


class IceWarpError(Exception):
    """Base class for all errors raised by this library."""


class IceWarpConnectionError(IceWarpError):
    """Raised when the IceWarp server cannot be reached (network/HTTP errors)."""


class IceWarpAuthenticationError(IceWarpError):
    """Raised when authentication (login) fails."""


class IceWarpAPIError(IceWarpError):
    """Raised when the IceWarp Maintenance API returns an error response.

    Attributes:
        command_name: The ``commandname`` that was sent.
        result: The parsed ``result`` value from the response, if any.
        raw_response: The parsed response dict (as returned by the XML codec).
    """

    def __init__(
        self,
        message: str,
        *,
        command_name: str | None = None,
        result: Any = None,
        raw_response: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.command_name = command_name
        self.result = result
        self.raw_response = raw_response

    def __str__(self) -> str:  # pragma: no cover - trivial
        base = super().__str__()
        if self.command_name:
            return f"{base} (command={self.command_name!r}, result={self.result!r})"
        return base
