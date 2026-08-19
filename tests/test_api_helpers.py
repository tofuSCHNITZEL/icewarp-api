"""Tests for hand-written, curated helpers on IceWarpAPI (not the generated .iw layer)."""

from icewarp_api.api import IceWarpAPI

BASE_URL = "http://icewarp.example.com/icewarpapi"


def xml_result(result_xml: str, sid: str = "sid-123") -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<iq sid="{sid}" type="result">'
        f'<query xmlns="admin:iq:rpc">{result_xml}</query></iq>'
    )


def test_get_all_accounts_across_multiple_domains(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetDomainsInfoList",
        text=xml_result(
            "<result>"
            "<item><name>example.com</name></item>"
            "<item><name>example.org</name></item>"
            "</result>"
        ),
    )

    def accounts_callback(request, context):
        body = request.body.decode("utf-8")
        if "example.com" in body:
            return xml_result(
                "<result><item><email>user1@example.com</email></item>"
                "<item><email>user2@example.com</email></item></result>"
            )
        return xml_result("<result><item><email>user1@example.org</email></item></result>")

    requests_mock.post(f"{BASE_URL}/GetAccountsInfoList", text=accounts_callback)

    api = IceWarpAPI(BASE_URL, sid="sid-123")
    accounts = api.get_all_accounts()

    assert len(accounts) == 3
    assert {a["email"] for a in accounts} == {
        "user1@example.com",
        "user2@example.com",
        "user1@example.org",
    }
    domains_seen = {a["domain"] for a in accounts}
    assert domains_seen == {"example.com", "example.org"}


def test_get_all_accounts_single_domain_skips_domain_listing(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetAccountsInfoList",
        text=xml_result("<result><item><email>user1@example.com</email></item></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    accounts = api.get_all_accounts(domain="example.com")

    assert len(accounts) == 1
    assert accounts[0]["email"] == "user1@example.com"
    assert accounts[0]["domain"] == "example.com"
    # GetDomainsInfoList should never have been called.
    assert not requests_mock.request_history or all(
        "GetDomainsInfoList" not in r.url for r in requests_mock.request_history
    )


def test_get_all_accounts_paginates_within_a_domain(requests_mock):
    call_count = {"n": 0}

    def accounts_callback(request, context):
        call_count["n"] += 1
        if call_count["n"] == 1:
            items = "".join(f"<item><email>user{i}@example.com</email></item>" for i in range(2))
            return xml_result(f"<result>{items}</result>")
        return xml_result("<result><item><email>user2@example.com</email></item></result>")

    requests_mock.post(f"{BASE_URL}/GetAccountsInfoList", text=accounts_callback)

    api = IceWarpAPI(BASE_URL, sid="sid-123")
    accounts = api.get_all_accounts(domain="example.com", page_size=2)

    assert call_count["n"] == 2
    assert len(accounts) == 3
    assert all(a["domain"] == "example.com" for a in accounts)


def test_get_all_accounts_empty_domain_returns_empty_list(requests_mock):
    requests_mock.post(f"{BASE_URL}/GetAccountsInfoList", text=xml_result("<result></result>"))
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    assert api.get_all_accounts(domain="empty.example.com") == []


def test_get_all_users_sends_typemask(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetAccountsInfoList",
        text=xml_result("<result><item><email>user1@example.com</email></item></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    users = api.get_all_users(domain="example.com")

    assert [entry["email"] for entry in users] == ["user1@example.com"]
    body = requests_mock.request_history[-1].body.decode("utf-8")
    assert "<filter><typemask>0</typemask></filter>" in body


def test_get_all_mailing_lists_sends_typemask(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetAccountsInfoList",
        text=xml_result("<result><item><email>list1@example.com</email></item></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    lists = api.get_all_mailing_lists(domain="example.com")

    assert [entry["email"] for entry in lists] == ["list1@example.com"]
    body = requests_mock.request_history[-1].body.decode("utf-8")
    assert "<filter><typemask>1</typemask></filter>" in body


def test_get_all_groups_sends_typemask(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetAccountsInfoList",
        text=xml_result("<result><item><email>group1@example.com</email></item></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    groups = api.get_all_groups(domain="example.com")

    assert [entry["email"] for entry in groups] == ["group1@example.com"]
    assert groups[0]["domain"] == "example.com"
    body = requests_mock.request_history[-1].body.decode("utf-8")
    assert "<filter><typemask>7</typemask></filter>" in body


def test_get_all_accounts_omits_filter_by_default(requests_mock):
    requests_mock.post(
        f"{BASE_URL}/GetAccountsInfoList",
        text=xml_result("<result><item><email>user1@example.com</email></item></result>"),
    )
    api = IceWarpAPI(BASE_URL, sid="sid-123")
    api.get_all_accounts(domain="example.com")

    body = requests_mock.request_history[-1].body.decode("utf-8")
    assert "<filter>" not in body

