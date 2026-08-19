"""Generic XML codec for the IceWarp Maintenance API.

The IceWarp Maintenance API uses a small, XMPP-``iq``-like RPC envelope for
*every* endpoint, regardless of which of the 174 operations is being called::

    <iq sid="SESSION_ID">
      <query xmlns="admin:iq:rpc">
        <commandname>getdomainsinfolist</commandname>
        <commandparams>
          <filter>
            <namemask>*</namemask>
          </filter>
          <offset>0</offset>
          <count>50</count>
        </commandparams>
      </query>
    </iq>

and responses look like::

    <iq sid="SESSION_ID" type="result">
      <query xmlns="admin:iq:rpc">
        <result>
          <item>
            <name>example.com</name>
            <desc>Example domain</desc>
          </item>
          <item>
            <name>example.org</name>
          </item>
        </result>
      </query>
    </iq>

Because plain XML allows any element to repeat as a sibling (unlike JSON),
list-like data (multiple ``<item>`` elements, ``TPropertyStringList``
parameters, ...) cannot be described precisely by the API's OpenAPI/JSON
schema export. Rather than hard coding the shape of every one of the ~580
schemas, this module implements a small generic, recursive codec:

* Building a request: any ``dict`` becomes nested elements, any ``list``
  value becomes repeated sibling elements using the same tag name, ``None``
  values are omitted (so optional parameters can simply be left out) and any
  other value is converted with ``str()``.
* Parsing a response: elements with children become ``dict`` (or ``list`` of
  ``dict``/``str`` when a tag repeats), leaf elements become ``str``, and the
  handful of attributes IceWarp uses (``sid``, ``type`` on ``<iq>``, ``xmlns``
  on ``<query>``) are merged into the resulting dict.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Union

XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
NAMESPACE = "admin:iq:rpc"

JSONLike = Union[dict[str, Any], list[Any], str, int, float, bool, None]


def build_request(
    command_name: str, params: dict[str, Any] | None = None, *, sid: str | None = None
) -> bytes:
    """Build the raw XML request body for a single IceWarp API call.

    Args:
        command_name: The lowercase ``commandname`` value (e.g. ``"authenticate"``,
            ``"getdomainsinfolist"``). Endpoint helpers pass this automatically.
        params: The ``commandparams`` payload. Nested dicts/lists are supported,
            ``None`` values are skipped so callers can pass every optional
            parameter unconditionally.
        sid: Session id obtained from a previous ``Authenticate`` call. Omitted
            from the request when ``None`` (used for the initial login calls).

    Returns:
        UTF-8 encoded XML bytes ready to be used as an HTTP request body.
    """
    root = ET.Element("iq")
    if sid:
        root.set("sid", sid)

    query = ET.SubElement(root, "query")
    query.set("xmlns", NAMESPACE)

    command_el = ET.SubElement(query, "commandname")
    command_el.text = command_name

    params_el = ET.SubElement(query, "commandparams")
    _build_children(params_el, params or {})

    body = ET.tostring(root, encoding="utf-8")
    return XML_DECLARATION.encode("utf-8") + body


def parse_response(xml_bytes: bytes | str) -> dict[str, Any]:
    """Parse a raw IceWarp API XML response into a plain nested ``dict``.

    Returns:
        A dict with the ``sid``/``type`` attributes of the root ``<iq>``
        element (when present) plus a ``query`` key containing the parsed
        ``<query>`` element (its ``xmlns`` attribute and ``result``/other
        children).
    """
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")
    root = ET.fromstring(xml_bytes)
    parsed = _element_to_value(root)
    if not isinstance(parsed, dict):
        # A root element with no children/attributes at all (should not
        # normally happen for this API) - normalize to an empty dict.
        return {}
    return parsed


def _build_children(parent: ET.Element, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                if item is None:
                    continue
                child = ET.SubElement(parent, key)
                _set_value(child, item)
        else:
            child = ET.SubElement(parent, key)
            _set_value(child, value)


def _set_value(element: ET.Element, value: Any) -> None:
    if isinstance(value, dict):
        _build_children(element, value)
    elif isinstance(value, bool):
        element.text = "1" if value else "0"
    else:
        element.text = str(value)


def _element_to_value(element: ET.Element) -> JSONLike:
    result: dict[str, Any] = dict(element.attrib)
    children = list(element)

    if not children:
        text = (element.text or "").strip()
        if result:
            if text:
                result["_text"] = text
            return result
        return text

    groups: dict[str, list[ET.Element]] = {}
    for child in children:
        groups.setdefault(_local_name(child.tag), []).append(child)

    for tag, elements in groups.items():
        if len(elements) == 1:
            result[tag] = _element_to_value(elements[0])
        else:
            result[tag] = [_element_to_value(el) for el in elements]

    return result


def _local_name(tag: str) -> str:
    """Strip an XML namespace (``{uri}local``) from an ElementTree tag name.

    The API always wraps ``<query>`` in the ``admin:iq:rpc`` default
    namespace; ElementTree applies that namespace to every descendant
    element when parsing, which we don't care about here.
    """
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag
