# icewarp-api

A Python client and CLI for the **IceWarp Maintenance (Admin) API** - the
same XML/RPC-style API IceWarp's WebAdmin console uses to manage domains,
accounts, rules, devices, certificates, licensing and more.

* **Full coverage**: a typed, documented Python method for all **174**
  documented endpoints, generated from IceWarp's own API specification and
  grouped into 14 categories (`domains`, `accounts`, `rules`, `devices`,
  `server`, ...), all under `api.iw`.
* **Clear raw vs. curated split**: `api.iw.*` is 100% generated and always a
  1:1 mirror of the documented API; everything else on `IceWarpAPI` (`login`,
  `logout`, and any future higher-level helpers) is hand-written.
* **Generic escape hatch**: call any endpoint directly by name via
  `api.iw.call(...)`, even ones not (yet) covered by a typed wrapper.
* **CLI included**: the `icewarp-api` command exposes the same 174 endpoints
  from your shell, with session caching so you don't need to re-authenticate
  for every call.
* **No hidden magic**: a thin `requests`-based transport, a small generic XML
  codec, and plain `dict`/`list` responses - easy to reason about and to
  extend.

> This library is a third-party, community client. It is not affiliated with
> or endorsed by IceWarp.

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Library structure: `api.iw` vs. `api`](#library-structure-apiiw-vs-api)
- [Authentication](#authentication)
- [Working with responses](#working-with-responses)
- [The generic `call()` escape hatch](#the-generic-call-escape-hatch)
- [Nested / list parameters](#nested--list-parameters)
- [Error handling](#error-handling)
- [API categories](#api-categories)
- [Command line interface](#command-line-interface)
- [Examples](#examples)
- [Development](#development)
- [License](#license)

## Installation

```bash
pip install icewarp-api
```

Requires Python 3.9+.

## Quick start

```python
from icewarp_api import IceWarpAPI

with IceWarpAPI(
    "https://mail.example.com:32001/icewarpapi",
    "admin@example.com",
    "hunter2",
) as api:
    domains = api.iw.domains.get_domains_info_list()
    for domain in domains["item"]:
        print(domain["name"], domain["accountcount"])
```

The `base_url` should point at your IceWarp server's Maintenance API mount
path, typically `/icewarpapi` (see the `servers` list in IceWarp's own API
documentation for the exact host/port - usually `32000` for HTTP and `32001`
for HTTPS). If you pass a URL that doesn't already contain `icewarpapi`
(e.g. just `https://mail.example.com:32001`), it is appended automatically.

The context manager authenticates on `__enter__` and always logs out on
`__exit__`, even if an exception is raised. Without the context manager:

```python
from icewarp_api import IceWarpAPI, IceWarpError

api = IceWarpAPI("https://mail.example.com:32001/icewarpapi", verify_ssl=False)
try:
    api.login("admin@example.com", "hunter2")
    print(api.iw.accounts.get_accounts_info_list(domainstr="example.com"))
except IceWarpError as exc:
    print(f"API error: {exc}")
finally:
    api.logout()
```

## Library structure: `api.iw` vs. `api`

`IceWarpAPI` deliberately separates two kinds of functionality:

* **`api.iw`** (`IceWarpRawAPI`) - raw, generated, 1:1 access to all 174
  documented endpoints, grouped by category (`api.iw.domains`,
  `api.iw.accounts`, `api.iw.sessions`, ...), plus the generic
  `api.iw.call(...)` escape hatch. Everything under `.iw` is regenerated
  straight from IceWarp's API specification by `scripts/generate_client.py`
  and is never hand-edited - what you see is exactly what the API documents,
  named to match.
* **`api`** (`IceWarpAPI` itself) - hand-written, curated functionality:
  session lifecycle (`login`, `logout`, `use_session`, `sid`,
  `is_authenticated`, `close`), plus higher-level convenience helpers such as
  `get_all_accounts()` (see below) that compose one or more calls under `.iw`
  internally, so they never collide with or get overwritten by regenerating
  the raw layer.

Rule of thumb: if a name matches a documented IceWarp endpoint exactly
(`GetDomainsInfoList`, `CreateAccount`, ...), it lives under `api.iw`. If
it's a Python-side convenience that doesn't correspond 1:1 to a single
endpoint, it lives directly on `api`.

### `get_all_accounts()`

`GetAccountsInfoList` is scoped to a single domain - there's no documented
endpoint that returns every account on the server at once. `get_all_accounts()`
handles this for you: it lists every domain, then paginates through the
accounts in each, returning one flat list (each account dict gets an added
`"domain"` key):

```python
for account in api.get_all_accounts():
    print(account["email"], account["domain"])

# Or restrict to a single domain (skips listing all domains):
api.get_all_accounts(domain="example.com")

# Tune the page size used while paginating through each domain's accounts:
api.get_all_accounts(page_size=200)
```

Also available from the CLI as `icewarp-api get-all-accounts [--domain ...] [--page-size ...]`.

## Authentication

`IceWarpAPI`/`IceWarpClient` support plain email/password login out of the
box (`POST /Authenticate`):

```python
api = IceWarpAPI(base_url, "admin@example.com", "hunter2")
api.login()          # or pass email/password here instead of the constructor
print(api.sid)        # the session id (sid) now used for every subsequent call
```

If you already have a session id (obtained elsewhere, e.g. through SSO, a
token exchange, or a previous login you cached yourself), you can reuse it
without logging in again:

```python
api = IceWarpAPI(base_url)
api.use_session("existing-sid-value")
```

Other authentication flows documented by the API (RSA challenge/digest,
`GetAuthToken`, `AuthenticateJWT`, `GetJWTToken`, `AuthenticateSSO`, OAuth
authorization, ...) are all available as typed methods too (see
`api.iw.sessions`, `api.iw.oauth`), or via the generic `api.iw.call(...)`
method - they're just not wired into the high level login/logout
convenience flow.

## Working with responses

Every method returns the parsed `result` of the response as plain Python
`dict`/`list`/`str` - there are no custom model classes to learn:

```python
>>> api.iw.domains.get_domains_info_list()
{'item': [{'name': 'example.com', 'desc': '', 'domaintype': '0', 'accountcount': '12'}]}
```

Because the underlying API is XML-based, a field that repeats becomes a
`list` and a field that appears once becomes a `dict` - so a single-domain
server will return `{'item': {...}}` instead of `{'item': [{...}]}`. Handle
both cases, e.g.:

```python
items = domains.get("item", [])
if isinstance(items, dict):
    items = [items]
```

Values are always strings (as XML has no native integer/boolean type) - cast
them yourself where needed, e.g. `int(domain["accountcount"])`.

## The generic `call()` escape hatch

Every one of the 174 typed methods is a thin wrapper around this:

```python
api.iw.call("GetDomainsInfoList", filter={"namemask": "*"}, count=10)
```

Use it directly for endpoints you'd rather not use a typed method for, or
for endpoints added to the API after this library was last regenerated.

## Nested / list parameters

Some endpoints accept nested objects (pass a `dict`) or repeated values
(pass a `list`), matching the shape IceWarp's XML API expects. A few
endpoints (`DeleteAccounts`, `AddAccountMembers`, `DeleteAccountMembers`,
...) expect a `TPropertyStringList`-shaped parameter for a list of strings;
use the `string_list()` helper for that:

```python
from icewarp_api.helpers import string_list

api.iw.accounts.delete_accounts(
    domainstr="example.com",
    accountlist=string_list(["user1@example.com", "user2@example.com"]),
)
```

## Error handling

```python
from icewarp_api import IceWarpAPIError, IceWarpAuthenticationError, IceWarpConnectionError

try:
    api.iw.domains.delete_domain(domainstr="does-not-exist.com")
except IceWarpAuthenticationError:
    ...  # login itself failed
except IceWarpConnectionError:
    ...  # could not reach the server / non-2xx HTTP status
except IceWarpAPIError as exc:
    print(exc.command_name, exc.result, exc.raw_response)
```

All exceptions derive from `icewarp_api.IceWarpError`.

## API categories

| Category (attribute on `api.iw`) | Endpoints | Examples |
| --- | --- | --- |
| `sessions` | 24 | `authenticate`, `logout`, `get_session_info`, `get_jwt_token` |
| `oauth` | 31 | `add_oauth_client`, `get_oauth_authorization_uri`, `verify_jwt_token` |
| `accounts` | 26 | `get_accounts_info_list`, `create_account`, `set_account_password` |
| `signup` | 20 | `signup_account`, `reset_password`, `get_captcha` |
| `rules` | 14 | `get_rules_info_list`, `add_rule`, `move_rule` |
| `domains` | 13 | `get_domains_info_list`, `create_domain`, `delete_domain` |
| `devices` | 8 | `get_devices_info_list`, `set_device_wipe` |
| `account_members` | 8 | `get_webmail_resources`, `set_admin_resources` |
| `service` | 8 | `get_services_info_list`, `start_service`, `get_traffic_charts` |
| `certificates` | 8 | `get_server_certificate_list`, `create_server_certificate` |
| `spam_queues` | 7 | queue management endpoints |
| `server` | 5 | `get_server_properties`, `set_server_properties` |
| `smart_discover` | 1 | SmartDiscover configuration |
| `license` | 1 | `get_license_info` |

Every method's docstring includes the original API description, parameters
and return value - use your editor's autocomplete/hover, or `help(...)`, e.g.
`help(api.iw.domains.get_domains_info_list)`.

## Command line interface

Installed automatically as `icewarp-api`. Running `icewarp-api --help` groups
commands into three clearly separated panels:

* **Client commands** - session/transport basics: `login`, `logout`,
  `whoami`, `status`, `call` (generic escape hatch), `version`.
* **Toolkit** - curated, higher-level helpers built on top of the raw API,
  such as `get-all-accounts` - the CLI equivalent of hand-written
  `IceWarpAPI` methods like `get_all_accounts()` in Python.
* **Raw API categories** - one group per category, each exposing the raw,
  generated, 1:1 endpoints (`domains`, `accounts`, `sessions`, ...) - the CLI
  equivalent of `api.iw.*` in Python.

`--url`/`-u`, `--email`/`-e`, `--password`/`-p`, `--insecure`, `--timeout`
and `--no-session-cache` are **global options** (defined on the base
`icewarp-api` command, not on `login` or any other sub-command) - they must
be placed **before** the sub-command name:

```bash
icewarp-api --help
icewarp-api domains --help
icewarp-api --url https://mail.example.com:32001/icewarpapi --email admin@example.com --password hunter2 login
icewarp-api domains get-domains-info-list
icewarp-api accounts get-accounts-info-list --domainstr example.com
icewarp-api get-all-accounts
icewarp-api call GetDomainsInfoList --param 'filter={"namemask": "*"}'
icewarp-api logout
```

`icewarp-api login --url ...` (options placed *after* `login`) will fail
with `No such option: --url` - always put global options right after
`icewarp-api` and before the sub-command.

`login` caches the session id **and the base URL** in
`~/.icewarp_api/session.json`, so you only need to pass `--url` (and
`--email`/`--password`) once, on `login` - every later command reuses the
cached URL/session automatically, with no flags needed at all:

```bash
icewarp-api --url https://mail.example.com:32001/icewarpapi --email admin@example.com --password hunter2 login
icewarp-api domains get-domains-info-list   # no --url needed
icewarp-api whoami                          # no --url needed
icewarp-api status                          # show what's cached, without calling the API
icewarp-api logout
```

`icewarp-api status` prints the cache file path and its contents
(`base_url`, `email`, `sid`) plus the currently effective configuration,
without making any API calls - useful to check whether `login` actually
cached a session, or what URL/session the next command would use.
`icewarp-api whoami` does the equivalent live check instead, by calling the
`GetSessionInfo` endpoint against the server.

Credentials/URL can also be provided via environment variables
(`ICEWARP_API_URL`, `ICEWARP_API_EMAIL`, `ICEWARP_API_PASSWORD`) instead of
`login`, e.g. for CI or scripting where you don't want a cached session file.
Pass `--no-session-cache` to disable reading/writing the cache file entirely.
See [`examples/cli_usage.md`](examples/cli_usage.md) for a full walkthrough.

## Examples

- [`examples/basic_usage.py`](examples/basic_usage.py) - login, list domains and accounts, logout.
- [`examples/context_manager_usage.py`](examples/context_manager_usage.py) - the `with IceWarpAPI(...) as api:` pattern.
- [`examples/generic_call_usage.py`](examples/generic_call_usage.py) - the `call()` escape hatch and `string_list()` helper.
- [`examples/list_all_accounts.py`](examples/list_all_accounts.py) - listing every account across all domains, with pagination.
- [`examples/cli_usage.md`](examples/cli_usage.md) - CLI walkthrough.

## Development

```bash
git clone https://github.com/tofuSCHNITZEL/icewarp-api.git
cd icewarp-api
pip install -e ".[dev]"
pytest
```

The typed wrapper methods under `src/icewarp_api/generated/` and the
`IceWarpAPI` facade (`src/icewarp_api/api.py`) are generated from
`API_doc.json` (IceWarp's OpenAPI export) rather than hand-written. If
`API_doc.json` is updated, regenerate them with:

```bash
python scripts/generate_client.py
```

`scripts/mock_server.py` is a tiny stand-in IceWarp server useful for manual
end-to-end testing of the client/CLI without a real IceWarp installation:

```bash
python scripts/mock_server.py 32000
icewarp-api --url http://127.0.0.1:32000/icewarpapi --email a@b.com --password x login
```

### Project layout

```
src/icewarp_api/
  client.py       - low level session/auth/transport (IceWarpClient)
  api.py          - high level facade (IceWarpAPI), wires client + generated/*
  xmlcodec.py      - generic dict <-> IceWarp XML request/response codec
  exceptions.py    - IceWarpError and subclasses
  helpers.py       - small ergonomic helpers (string_list, ...)
  cli.py           - Typer CLI (`icewarp-api` console script)
  generated/       - one typed wrapper class per API category (auto-generated)
scripts/
  generate_client.py - regenerates src/icewarp_api/generated/ and api.py from API_doc.json
  mock_server.py     - minimal fake IceWarp server for manual testing
tests/             - pytest suite (uses requests-mock, no live server required)
examples/          - runnable usage examples + CLI walkthrough
```

## License

MIT - see [`LICENSE`](LICENSE).
