"""Tests for the icewarp_api CLI (Typer app)."""

from typer.testing import CliRunner

from icewarp_api import cli

runner = CliRunner()

BASE_URL = "http://icewarp.example.com/icewarpapi"


def xml_result(result_xml: str, sid: str = "sid-123") -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<iq sid="{sid}" type="result">'
        f'<query xmlns="admin:iq:rpc">{result_xml}</query></iq>'
    )


def isolate_session_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cli, "SESSION_FILE", tmp_path / "session.json")


def test_help():
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    assert "domains" in result.stdout
    assert "accounts" in result.stdout


def test_help_separates_high_level_and_raw_commands_into_panels():
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    assert cli.HIGH_LEVEL_PANEL in result.stdout
    assert cli.TOOLKIT_PANEL in result.stdout
    assert cli.RAW_API_PANEL in result.stdout

    high_level_idx = result.stdout.index(cli.HIGH_LEVEL_PANEL)
    toolkit_idx = result.stdout.index(cli.TOOLKIT_PANEL)
    raw_idx = result.stdout.index(cli.RAW_API_PANEL)
    assert high_level_idx < toolkit_idx < raw_idx

    # Session/client commands are listed within the high-level panel section.
    client_section = result.stdout[high_level_idx:toolkit_idx]
    for command in ["login", "logout", "whoami", "status", "call", "version"]:
        assert command in client_section, f"{command!r} should be listed under the client commands panel"

    # Curated helpers are listed within the toolkit panel section.
    toolkit_section = result.stdout[toolkit_idx:raw_idx]
    assert "get-all-accounts" in toolkit_section

    # Raw category groups are listed after the raw API panel starts.
    raw_section = result.stdout[raw_idx:]
    for category in ["domains", "accounts", "sessions", "oauth"]:
        assert category in raw_section, f"{category!r} should be listed under the raw API panel"


def test_version():
    result = runner.invoke(cli.app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_domains_subcommand_help():
    result = runner.invoke(cli.app, ["domains", "--help"])
    assert result.exit_code == 0
    assert "get-domains-info-list" in result.stdout


def test_status_with_no_cached_session(monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 0, result.stdout
    assert '"cached_session": null' in result.stdout
    assert "No cached session found" in result.stdout


def test_status_shows_cached_session(monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    (tmp_path / "session.json").write_text(
        '{"base_url": "%s", "email": "admin@example.com", "sid": "sid-123"}' % BASE_URL
    )
    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 0, result.stdout
    assert BASE_URL in result.stdout
    assert "admin@example.com" in result.stdout
    assert "sid-123" in result.stdout
    assert "No cached session found" not in result.stdout


def test_status_notes_when_cache_disabled(monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    result = runner.invoke(cli.app, ["--no-session-cache", "status"])
    assert result.exit_code == 0, result.stdout
    assert "--no-session-cache is set" in result.stdout


def test_login_and_cached_session_reuse(requests_mock, monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    requests_mock.post(f"{BASE_URL}/Authenticate", text=xml_result("<result>1</result>"))
    requests_mock.post(
        f"{BASE_URL}/GetSessionInfo", text=xml_result("<result><email>admin@example.com</email></result>")
    )
    requests_mock.post(
        f"{BASE_URL}/GetDomainsInfoList",
        text=xml_result("<result><item><name>example.com</name></item></result>"),
    )

    login_result = runner.invoke(
        cli.app,
        ["--url", BASE_URL, "--email", "admin@example.com", "--password", "secret", "login"],
    )
    assert login_result.exit_code == 0, login_result.stdout
    assert "Logged in" in login_result.stdout
    assert (tmp_path / "session.json").exists()

    # Subsequent calls should reuse the cached sid AND base_url (no --url,
    # --email or --password needed at all).
    domains_result = runner.invoke(cli.app, ["domains", "get-domains-info-list"])
    assert domains_result.exit_code == 0, domains_result.stdout
    assert "example.com" in domains_result.stdout


def test_cached_url_is_used_without_passing_url_flag(requests_mock, monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    (tmp_path / "session.json").write_text('{"base_url": "%s", "email": "a@b.com", "sid": "sid-123"}' % BASE_URL)
    requests_mock.post(
        f"{BASE_URL}/GetSessionInfo", text=xml_result("<result><email>a@b.com</email></result>")
    )
    requests_mock.post(
        f"{BASE_URL}/GetDomainsInfoList",
        text=xml_result("<result><item><name>example.com</name></item></result>"),
    )

    # No --url/--email/--password anywhere on the command line.
    result = runner.invoke(cli.app, ["domains", "get-domains-info-list"])
    assert result.exit_code == 0, result.stdout
    assert "example.com" in result.stdout

    result = runner.invoke(cli.app, ["whoami"])
    assert result.exit_code == 0, result.stdout
    assert "a@b.com" in result.stdout


def test_call_generic_passthrough(requests_mock, monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    requests_mock.post(
        f"{BASE_URL}/GetDomainsInfoList",
        text=xml_result("<result><item><name>example.com</name></item></result>"),
    )
    (tmp_path / "session.json").write_text('{"base_url": "%s", "email": "a@b.com", "sid": "sid-123"}' % BASE_URL)
    requests_mock.post(
        f"{BASE_URL}/GetSessionInfo", text=xml_result("<result><email>a@b.com</email></result>")
    )

    result = runner.invoke(cli.app, ["call", "GetDomainsInfoList"])
    assert result.exit_code == 0, result.stdout
    assert "example.com" in result.stdout


def test_get_all_accounts_command(requests_mock, monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    (tmp_path / "session.json").write_text('{"base_url": "%s", "email": "a@b.com", "sid": "sid-123"}' % BASE_URL)
    requests_mock.post(
        f"{BASE_URL}/GetSessionInfo", text=xml_result("<result><email>a@b.com</email></result>")
    )
    requests_mock.post(
        f"{BASE_URL}/GetDomainsInfoList",
        text=xml_result("<result><item><name>example.com</name></item></result>"),
    )
    requests_mock.post(
        f"{BASE_URL}/GetAccountsInfoList",
        text=xml_result("<result><item><email>user@example.com</email></item></result>"),
    )

    result = runner.invoke(cli.app, ["get-all-accounts"])
    assert result.exit_code == 0, result.stdout
    assert "user@example.com" in result.stdout
    assert "example.com" in result.stdout


def test_get_all_accounts_command_with_domain_filter(requests_mock, monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    (tmp_path / "session.json").write_text('{"base_url": "%s", "email": "a@b.com", "sid": "sid-123"}' % BASE_URL)
    requests_mock.post(
        f"{BASE_URL}/GetSessionInfo", text=xml_result("<result><email>a@b.com</email></result>")
    )
    requests_mock.post(
        f"{BASE_URL}/GetAccountsInfoList",
        text=xml_result("<result><item><email>user@example.com</email></item></result>"),
    )

    result = runner.invoke(cli.app, ["get-all-accounts", "--domain", "example.com"])
    assert result.exit_code == 0, result.stdout
    assert "user@example.com" in result.stdout
    # GetDomainsInfoList should not have been called when --domain is given.
    assert all("GetDomainsInfoList" not in r.url for r in requests_mock.request_history)


def test_missing_credentials_errors_cleanly(monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    result = runner.invoke(cli.app, ["--url", BASE_URL, "domains", "get-domains-info-list"])
    assert result.exit_code == 1
    assert "Not authenticated" in result.stdout or "Not authenticated" in (result.stderr or "")


def test_missing_url_errors_cleanly(monkeypatch, tmp_path):
    isolate_session_cache(monkeypatch, tmp_path)
    result = runner.invoke(cli.app, ["domains", "get-domains-info-list"])
    assert result.exit_code == 1
