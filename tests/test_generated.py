"""Spot-checks for a handful of the generated, typed API wrapper methods."""

from icewarp_api.api import IceWarpAPI

BASE_URL = "http://icewarp.example.com/icewarpapi"


def xml_result(result_xml: str, sid: str = "sid-123") -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<iq sid="{sid}" type="result">'
        f'<query xmlns="admin:iq:rpc">{result_xml}</query></iq>'
    )


def test_domains_get_domains_info_list(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetDomainsInfoList",
        text=xml_result("<result><item><name>example.com</name></item></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    result = api.iw.domains.get_domains_info_list(offset=0, count=10)
    assert result == {"item": {"name": "example.com"}}
    sent = requests_mock.last_request.body.decode("utf-8")
    assert "<commandname>getdomainsinfolist</commandname>" in sent
    assert "<offset>0</offset>" in sent
    assert "<count>10</count>" in sent
    assert "<filter>" not in sent  # omitted since not passed


def test_domains_delete_domain(requests_mock):
    requests_mock.post(f"{BASE_URL}/DeleteDomain", text=xml_result("<result>1</result>"))
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    result = api.iw.domains.delete_domain(domainstr="example.com")
    assert result == "1"
    sent = requests_mock.last_request.body.decode("utf-8")
    assert "<domainstr>example.com</domainstr>" in sent


def test_accounts_get_accounts_info_list(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetAccountsInfoList",
        text=xml_result("<result><item><email>user@example.com</email></item></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    result = api.iw.accounts.get_accounts_info_list(domainstr="example.com")
    assert result == {"item": {"email": "user@example.com"}}


def test_server_get_server_properties(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetServerProperties",
        text=xml_result("<result><hostname>mail.example.com</hostname></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    result = api.iw.server.get_server_properties()
    assert result == {"hostname": "mail.example.com"}


def test_license_get_license_info_has_no_params(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetLicenseInfo",
        text=xml_result("<result><licensed>1</licensed></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    result = api.iw.license.get_license_info()
    assert result == {"licensed": "1"}
    sent = requests_mock.last_request.body.decode("utf-8")
    assert "<commandparams />" in sent or "<commandparams/>" in sent


def test_keyword_collision_param_is_renamed_but_sent_correctly(requests_mock):
    # `from` is a Python keyword; the generated parameter name should be
    # `from_` while still sending `<from>` in the request body.
    requests_mock.post(
        f"{BASE_URL}/GetAccountChatHistory",
        text=xml_result("<result>1</result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    result = api.iw.sessions.get_account_chat_history(from_="a@example.com", to_="b@example.com")
    assert result == "1"
    sent = requests_mock.last_request.body.decode("utf-8")
    assert "<from>a@example.com</from>" in sent
    assert "<to_>b@example.com</to_>" in sent


def test_all_generated_category_classes_are_wired_into_facade(requests_mock):
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    for attr in [
        "sessions",
        "oauth",
        "accounts",
        "signup",
        "rules",
        "domains",
        "devices",
        "account_members",
        "service",
        "certificates",
        "spam_queues",
        "server",
        "smart_discover",
        "license",
    ]:
        assert hasattr(api.iw, attr), f"IceWarpAPI.iw is missing the '{attr}' category"


def test_iw_call_generic_passthrough(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetDomainsInfoList",
        text=xml_result("<result><item><name>example.com</name></item></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    result = api.iw.call("GetDomainsInfoList")
    assert result == {"item": {"name": "example.com"}}


def test_raw_calls_are_not_exposed_at_top_level(requests_mock):
    # Raw/generated access must live under .iw, never directly on IceWarpAPI,
    # so future hand-written helpers can be added at the top level without
    # ever colliding with codegen.
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    for attr in ["domains", "accounts", "sessions", "call"]:
        assert not hasattr(api, attr), f"IceWarpAPI should not expose raw '.{attr}' directly - use '.iw.{attr}'"
