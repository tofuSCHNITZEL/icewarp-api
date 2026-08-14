"""Tests for icewarp_api.xmlcodec."""

from icewarp_api import xmlcodec


def test_build_request_basic():
    body = xmlcodec.build_request("authenticate", {"email": "a@b.com", "password": "secret"}, sid=None)
    text = body.decode("utf-8")
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<commandname>authenticate</commandname>" in text
    assert "<email>a@b.com</email>" in text
    assert "<password>secret</password>" in text
    assert 'sid="' not in text  # sid omitted when None


def test_build_request_includes_sid():
    body = xmlcodec.build_request("logout", {}, sid="my-session-id")
    text = body.decode("utf-8")
    assert '<iq sid="my-session-id">' in text
    assert "<commandparams />" in text or "<commandparams/>" in text


def test_build_request_skips_none_values():
    body = xmlcodec.build_request("x", {"a": "1", "b": None}, sid=None)
    text = body.decode("utf-8")
    assert "<a>1</a>" in text
    assert "<b>" not in text


def test_build_request_nested_dict():
    body = xmlcodec.build_request(
        "getdomainsinfolist", {"filter": {"namemask": "*"}, "offset": 0, "count": 50}, sid=None
    )
    text = body.decode("utf-8")
    assert "<filter><namemask>*</namemask></filter>" in text
    assert "<offset>0</offset>" in text
    assert "<count>50</count>" in text


def test_build_request_repeated_list_items():
    body = xmlcodec.build_request(
        "deleteaccounts",
        {"accountlist": {"classname": "tpropertystringlist", "val": {"item": ["a@b.com", "c@d.com"]}}},
        sid=None,
    )
    text = body.decode("utf-8")
    assert text.count("<item>") == 2
    assert "<item>a@b.com</item>" in text
    assert "<item>c@d.com</item>" in text


def test_parse_response_simple_result():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <iq sid="s1" type="result"><query xmlns="admin:iq:rpc"><result>1</result></query></iq>"""
    parsed = xmlcodec.parse_response(xml)
    assert parsed["sid"] == "s1"
    assert parsed["type"] == "result"
    assert parsed["query"]["result"] == "1"


def test_parse_response_strips_namespace_and_handles_repeated_items():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <iq sid="s1" type="result">
      <query xmlns="admin:iq:rpc">
        <result>
          <item><name>example.com</name></item>
          <item><name>example.org</name></item>
        </result>
      </query>
    </iq>"""
    parsed = xmlcodec.parse_response(xml)
    result = parsed["query"]["result"]
    assert "item" in result
    assert isinstance(result["item"], list)
    assert [i["name"] for i in result["item"]] == ["example.com", "example.org"]


def test_parse_response_single_item_is_not_a_list():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <iq sid="s1" type="result">
      <query xmlns="admin:iq:rpc">
        <result><item><name>example.com</name></item></result>
      </query>
    </iq>"""
    parsed = xmlcodec.parse_response(xml)
    result = parsed["query"]["result"]
    assert isinstance(result["item"], dict)
    assert result["item"]["name"] == "example.com"


def test_roundtrip_build_then_parse_like_shape():
    # Building a request and parsing a response both use the same generic
    # codec; sanity check that a "result" mirroring what we sent parses back
    # to the same nested structure.
    body = xmlcodec.build_request("test", {"filter": {"namemask": "*"}}, sid="s1")
    assert b'sid="s1"' in body
    parsed = xmlcodec.parse_response(
        b'<iq sid="s1" type="result"><query xmlns="admin:iq:rpc">'
        b"<result><namemask>*</namemask></result></query></iq>"
    )
    assert parsed["query"]["result"]["namemask"] == "*"
