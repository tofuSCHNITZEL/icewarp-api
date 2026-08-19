"""Small ergonomic helpers for building IceWarp API request parameters."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def string_list(values: Iterable[Any]) -> dict[str, Any]:
    """Build a ``TPropertyStringList``-shaped parameter.

    Several endpoints (``DeleteAccounts``, ``AddAccountMembers``,
    ``DeleteAccountMembers``, ...) expect a list of strings encoded as::

        <accountlist>
          <classname>tpropertystringlist</classname>
          <val>
            <item>user1@example.com</item>
            <item>user2@example.com</item>
          </val>
        </accountlist>

    This helper builds the dict shape expected by :func:`icewarp_api.xmlcodec.build_request`
    for that pattern, so it can be passed directly as a parameter value, e.g.::

        api.iw.accounts.delete_accounts(
            domainstr="example.com",
            accountlist=string_list(["user1@example.com", "user2@example.com"]),
        )
    """
    return {"classname": "tpropertystringlist", "val": {"item": list(values)}}


def as_bool_flag(value: bool) -> str:
    """Convert a Python bool to the ``"1"``/``"0"`` string flag IceWarp expects."""
    return "1" if value else "0"


def as_list(value: Any | None) -> list[Any]:
    """Normalize an XML-derived ``item`` field to a list.

    Because the underlying API is XML-based, a field that repeats becomes a
    ``list`` while a field that appears exactly once becomes a plain ``dict``
    (or other scalar) instead of a single-element list - e.g. a
    single-domain server returns ``{'item': {...}}`` rather than
    ``{'item': [{...}]}``. This helper normalizes both cases (and ``None``)
    to a list, so callers can always iterate uniformly::

        result = api.iw.domains.get_domains_info_list()
        for domain in as_list(result.get("item")):
            ...
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
