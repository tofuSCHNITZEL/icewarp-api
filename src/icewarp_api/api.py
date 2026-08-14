"""High level facade for the IceWarp Maintenance API.

``IceWarpAPI`` is hand-written and never regenerated - it wraps
:class:`~icewarp_api.client.IceWarpClient` (session/authentication handling)
and exposes:

* ``.iw`` - raw, generated, 1:1 access to all 174 documented endpoints (see
  :class:`~icewarp_api.generated.raw_api.IceWarpRawAPI`, produced from
  ``API_doc.json`` by ``scripts/generate_client.py``).
* Session lifecycle: :meth:`~IceWarpAPI.login`, :meth:`~IceWarpAPI.logout`,
  :meth:`~IceWarpAPI.use_session`, :attr:`~IceWarpAPI.sid`,
  :attr:`~IceWarpAPI.is_authenticated`, :meth:`~IceWarpAPI.close`.
* Curated, higher-level helpers that compose one or more calls under ``.iw``
  (e.g. :meth:`~IceWarpAPI.get_all_accounts`) - this is where any future
  convenience helpers belong, since ``.iw``/``generated/`` must stay a pure
  1:1 mirror of the documented API.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from .client import IceWarpClient, DEFAULT_TIMEOUT
from .generated.raw_api import IceWarpRawAPI
from .helpers import as_list

DEFAULT_PAGE_SIZE = 100


class IceWarpAPI:
    """Batteries-included, high level client for the IceWarp Maintenance API.

    Wraps :class:`IceWarpClient` (session/authentication handling) and
    exposes:

    * Session lifecycle: :meth:`login`, :meth:`logout`, :meth:`use_session`,
      :attr:`sid`, :attr:`is_authenticated`, :meth:`close`.
    * ``.iw`` - raw, 1:1 access to all 174 documented endpoints, see
      :class:`~icewarp_api.generated.raw_api.IceWarpRawAPI`.
    * Curated helpers such as :meth:`get_all_accounts` that compose one or
      more raw calls for you.

    Any future hand-written, higher-level convenience helpers belong
    directly on this class instead of inside ``.iw`` - that namespace is
    fully regenerated from ``API_doc.json`` and must stay a pure 1:1 mirror
    of the documented API.

    Example:
        >>> with IceWarpAPI(
        ...     "https://mail.example.com:32001/icewarpapi",
        ...     "admin@example.com",
        ...     "hunter2",
        ...     verify_ssl=False,
        ... ) as api:
        ...     for domain in api.iw.domains.get_domains_info_list()['item']:
        ...         print(domain['name'])
    """

    def __init__(
        self,
        base_url: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        *,
        auth_type: str = "plain",
        timeout: float = DEFAULT_TIMEOUT,
        verify_ssl: bool = True,
        session: Optional[requests.Session] = None,
        sid: Optional[str] = None,
    ) -> None:
        self.client = IceWarpClient(
            base_url,
            email,
            password,
            auth_type=auth_type,
            timeout=timeout,
            verify_ssl=verify_ssl,
            session=session,
            sid=sid,
        )
        self.iw = IceWarpRawAPI(self.client)

    # -- session/auth lifecycle ---------------------------------------------

    @property
    def sid(self) -> Optional[str]:
        """The current session id, or ``None`` if not authenticated."""
        return self.client.sid

    @property
    def is_authenticated(self) -> bool:
        return self.client.is_authenticated

    def login(self, *args: Any, **kwargs: Any) -> str:
        """Authenticate with plain email/password. See ``IceWarpClient.login``."""
        return self.client.login(*args, **kwargs)

    def use_session(self, sid: str) -> None:
        """Reuse an existing session id obtained elsewhere (skip login)."""
        self.client.use_session(sid)

    def logout(self) -> None:
        """Log out and invalidate the current session, if any."""
        self.client.logout()

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "IceWarpAPI":
        self.client.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return self.client.__exit__(exc_type, exc, tb)

    # -- curated, higher-level helpers ---------------------------------------

    def get_all_accounts(
        self, *, domain: Optional[str] = None, page_size: int = DEFAULT_PAGE_SIZE
    ) -> List[Dict[str, Any]]:
        """Fetch every account on the server, across all domains.

        IceWarp's ``GetAccountsInfoList`` endpoint (``api.iw.accounts.get_accounts_info_list``)
        is scoped to a single domain - there is no single "all accounts on
        the server" endpoint. This helper lists every domain (via
        ``GetDomainsInfoList``, unless ``domain`` is given), then lists and
        paginates through the accounts in each, returning a flat list. Each
        account dict has an extra ``"domain"`` key added so you know which
        domain it came from.

        Args:
            domain: Only fetch accounts for this domain name, instead of
                every domain on the server.
            page_size: Number of accounts requested per page while
                paginating through ``GetAccountsInfoList``.

        Returns:
            A list of account dicts (as returned by ``GetAccountsInfoList``),
            each with an added ``"domain"`` key.

        Example:
            >>> for account in api.get_all_accounts():
            ...     print(account["email"], account["domain"])
        """
        if domain is not None:
            domain_names = [domain]
        else:
            domains_result = self.iw.domains.get_domains_info_list()
            domain_items = as_list(
                domains_result.get("item") if isinstance(domains_result, dict) else None
            )
            domain_names = [d["name"] for d in domain_items]

        accounts: List[Dict[str, Any]] = []
        for domain_name in domain_names:
            offset = 0
            while True:
                result = self.iw.accounts.get_accounts_info_list(
                    domainstr=domain_name, offset=offset, count=page_size
                )
                items = as_list(result.get("item") if isinstance(result, dict) else None)
                if not items:
                    break
                for account in items:
                    account["domain"] = domain_name
                    accounts.append(account)
                if len(items) < page_size:
                    break
                offset += page_size

        return accounts
