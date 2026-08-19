"""Tests for icewarp_api.client.IceWarpClient."""

import pytest

from icewarp_api.client import IceWarpClient, _normalize_base_url
from icewarp_api.exceptions import (
    IceWarpAPIError,
    IceWarpAuthenticationError,
    IceWarpConnectionError,
)

BASE_URL = "http://icewarp.example.com/icewarpapi"


def xml_result(result_xml: str, sid: str = "sid-123", type_: str = "result") -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<iq sid="{sid}" type="{type_}">'
        f'<query xmlns="admin:iq:rpc">{result_xml}</query></iq>'
    )


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://mail.example.com:32001", "https://mail.example.com:32001/icewarpapi"),
        ("https://mail.example.com:32001/", "https://mail.example.com:32001/icewarpapi"),
        ("https://mail.example.com:32001/icewarpapi", "https://mail.example.com:32001/icewarpapi"),
        ("https://mail.example.com:32001/icewarpapi/", "https://mail.example.com:32001/icewarpapi"),
        ("https://mail.example.com:32001/IceWarpAPI", "https://mail.example.com:32001/IceWarpAPI"),
        ("http://127.0.0.1:32000", "http://127.0.0.1:32000/icewarpapi"),
    ],
)
def test_normalize_base_url_appends_suffix_when_missing(raw, expected):
    assert _normalize_base_url(raw) == expected


def test_client_normalizes_base_url_without_icewarpapi_suffix():
    client = IceWarpClient("https://mail.example.com:32001")
    assert client.base_url == "https://mail.example.com:32001/icewarpapi"


def test_login_stores_sid(requests_mock):
    requests_mock.post(f"{BASE_URL}/Authenticate", text=xml_result("<result>1</result>"))
    client = IceWarpClient(BASE_URL)
    sid = client.login("admin@example.com", "hunter2")
    assert sid == "sid-123"
    assert client.sid == "sid-123"
    assert client.is_authenticated

    sent_body = requests_mock.last_request.body.decode("utf-8")
    assert "<email>admin@example.com</email>" in sent_body
    assert "<password>hunter2</password>" in sent_body
    assert 'sid="' not in sent_body  # no sid on the initial login request


def test_login_requires_credentials():
    client = IceWarpClient(BASE_URL)
    with pytest.raises(IceWarpAuthenticationError):
        client.login()


def test_login_without_sid_in_response_raises(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/Authenticate",
        text='<?xml version="1.0"?><iq type="result"><query xmlns="admin:iq:rpc"><result>0</result></query></iq>',
    )
    client = IceWarpClient(BASE_URL)
    with pytest.raises(IceWarpAuthenticationError):
        client.login("admin@example.com", "hunter2")


def test_call_sends_sid_and_returns_result(requests_mock):
    requests_mock.post(f"{BASE_URL}/Authenticate", text=xml_result("<result>1</result>"))
    requests_mock.post(
        f"{BASE_URL}/GetDomainsInfoList",
        text=xml_result("<result><item><name>example.com</name></item></result>"),
    )
    client = IceWarpClient(BASE_URL)
    client.login("admin@example.com", "hunter2")
    result = client.call("GetDomainsInfoList")
    assert result == {"item": {"name": "example.com"}}

    sent_body = requests_mock.last_request.body.decode("utf-8")
    assert 'sid="sid-123"' in sent_body
    assert "<commandname>getdomainsinfolist</commandname>" in sent_body


def test_call_with_none_params_omits_them(requests_mock):
    requests_mock.post(f"{BASE_URL}/GetDomainsInfoList", text=xml_result("<result>1</result>"))
    client = IceWarpClient(BASE_URL, sid="sid-123")
    client.call("GetDomainsInfoList", filter=None, offset=0, count=50)
    sent_body = requests_mock.last_request.body.decode("utf-8")
    assert "<filter>" not in sent_body
    assert "<offset>0</offset>" in sent_body
    assert "<count>50</count>" in sent_body


def test_error_response_raises_api_error(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/DeleteDomain",
        text=xml_result("<result>-1</result>", type_="error"),
    )
    client = IceWarpClient(BASE_URL, sid="sid-123")
    with pytest.raises(IceWarpAPIError):
        client.call("DeleteDomain", domainstr="example.com")


def test_http_error_status_raises_connection_error(requests_mock):
    requests_mock.post(f"{BASE_URL}/GetDomainsInfoList", status_code=500, text="boom")
    client = IceWarpClient(BASE_URL, sid="sid-123")
    with pytest.raises(IceWarpConnectionError):
        client.call("GetDomainsInfoList")


def test_logout_clears_sid(requests_mock):
    requests_mock.post(f"{BASE_URL}/Logout", text=xml_result("<result>1</result>"))
    client = IceWarpClient(BASE_URL, sid="sid-123")
    client.logout()
    assert client.sid is None
    assert not client.is_authenticated


def test_logout_noop_when_not_authenticated(requests_mock):
    client = IceWarpClient(BASE_URL)
    client.logout()  # should not raise / not make any HTTP request
    assert requests_mock.call_count == 0


def test_context_manager_logs_in_and_out(requests_mock):
    requests_mock.post(f"{BASE_URL}/Authenticate", text=xml_result("<result>1</result>"))
    requests_mock.post(f"{BASE_URL}/Logout", text=xml_result("<result>1</result>"))
    with IceWarpClient(BASE_URL, "admin@example.com", "hunter2") as client:
        assert client.is_authenticated
    assert not client.is_authenticated


def test_use_session_reuses_existing_sid(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetSessionInfo",
        text=xml_result("<result><email>admin@example.com</email></result>"),
    )
    client = IceWarpClient(BASE_URL)
    client.use_session("existing-sid")
    result = client.call("GetSessionInfo")
    assert result == {"email": "admin@example.com"}
    sent_body = requests_mock.last_request.body.decode("utf-8")
    assert 'sid="existing-sid"' in sent_body
