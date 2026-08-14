"""Package init for icewarp_api.

Exposes the high level facade (:class:`IceWarpAPI`), the low level
transport client (:class:`IceWarpClient`) and the public exceptions.
"""

from .client import IceWarpClient
from .exceptions import (
    IceWarpAPIError,
    IceWarpAuthenticationError,
    IceWarpConnectionError,
    IceWarpError,
)
from .api import IceWarpAPI

__version__ = "0.1.0"

__all__ = [
    "IceWarpAPI",
    "IceWarpClient",
    "IceWarpError",
    "IceWarpAPIError",
    "IceWarpAuthenticationError",
    "IceWarpConnectionError",
    "__version__",
]
