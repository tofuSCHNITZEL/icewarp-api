"""Package init for icewarp_api.

Exposes the high level facade (:class:`IceWarpAPI`), the low level
transport client (:class:`IceWarpClient`) and the public exceptions.
"""

from .api import AccountType, IceWarpAPI
from .client import IceWarpClient
from .exceptions import (
    IceWarpAPIError,
    IceWarpAuthenticationError,
    IceWarpConnectionError,
    IceWarpError,
)

__version__ = "0.1.0"

__all__ = [
    "AccountType",
    "IceWarpAPI",
    "IceWarpAPIError",
    "IceWarpAuthenticationError",
    "IceWarpClient",
    "IceWarpConnectionError",
    "IceWarpError",
    "__version__",
]
