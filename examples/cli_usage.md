# CLI usage examples

The `icewarp-api` command is installed automatically with the package
(`pip install icewarp-api`). It exposes every category of the API as a
sub-command group, a generic `call` passthrough, and `login`/`logout`/
`whoami` helpers.

Credentials and the server URL can be passed as flags or via environment
variables, which is usually more convenient:

```bash
export ICEWARP_API_URL="https://mail.example.com:32001/icewarpapi"
export ICEWARP_API_EMAIL="admin@example.com"
export ICEWARP_API_PASSWORD="hunter2"
```

> **Option order matters:** `--url`/`-u`, `--email`/`-e`, `--password`/`-p`,
> `--insecure`, `--timeout` and `--no-session-cache` are **global options**
> defined on the base `icewarp-api` command - not on `login`, `domains`, or
> any other sub-command. They must come **before** the sub-command name,
> e.g. `icewarp-api --url ... --email ... --password ... login`, **not**
> `icewarp-api login --url ...` (which fails with `No such option: --url`).
> Using environment variables (as above) avoids this ordering requirement
> entirely.

## Explore available commands

```bash
icewarp-api --help
icewarp-api domains --help
icewarp-api accounts --help
```

`icewarp-api --help` groups commands into three panels: **Client commands**
(session/transport basics - `login`, `logout`, `whoami`, `status`, `call`,
`version`), **Toolkit** (curated, higher-level helpers built on the raw API
- currently `get-all-accounts`), and **Raw API categories** (one group per
category exposing the raw, generated, 1:1 endpoints - `domains`, `accounts`,
`sessions`, ...). This mirrors the Python library's split between `api`
(session lifecycle), curated helpers on `api` (e.g. `get_all_accounts()`),
and `api.iw` (raw).

## Log in once, reuse the session for later calls

`login` caches the session id **and the base URL** in
`~/.icewarp_api/session.json`. Every later command automatically reuses
both, so you don't need to pass `--url`, `--email` or `--password` again
until the cached session is cleared (via `logout` or `--no-session-cache`):

```bash
icewarp-api --url https://mail.example.com:32001/icewarpapi --email admin@example.com --password hunter2 login
# Logged in as admin@example.com. Session id: ...
# Cached session (including the API URL) - later calls don't need --url/--email/--password.

icewarp-api domains get-domains-info-list
icewarp-api accounts get-accounts-info-list --domainstr example.com
icewarp-api whoami

icewarp-api logout
```

If `ICEWARP_API_URL`/`ICEWARP_API_EMAIL`/`ICEWARP_API_PASSWORD` are set (see
above), you can skip passing anything at all to `login`:

```bash
icewarp-api login
```

## Check the cached session / current config

`icewarp-api status` reads `~/.icewarp_api/session.json` and prints its
contents (`base_url`, `email`, `sid`) plus what would actually be used for
the next command - all **without** making any API calls:

```bash
icewarp-api status
```

```json
{
  "session_cache_file": "/home/you/.icewarp_api/session.json",
  "session_cache_enabled": true,
  "cached_session": {
    "base_url": "https://mail.example.com:32001/icewarpapi",
    "email": "admin@example.com",
    "sid": "..."
  },
  "effective_base_url": "https://mail.example.com:32001/icewarpapi",
  "verify_ssl": true,
  "timeout": 30.0
}
```

`icewarp-api whoami` does the live equivalent: it calls the `GetSessionInfo`
endpoint on the server to confirm the cached session is actually still
valid, rather than just showing what's on disk.

## List domains, pretty-printed as JSON

```bash
icewarp-api domains get-domains-info-list --count 10
```

```json
{
  "item": [
    {
      "name": "example.com",
      "desc": "Example domain",
      "domaintype": "0",
      "accountcount": "12"
    }
  ]
}
```

## Filter/nested parameters as JSON

Parameters that map to nested objects (`filter`, `serverpropertylist`, ...)
accept a JSON string:

```bash
icewarp-api domains get-domains-info-list --filter '{"namemask": "*.com"}'
```

## Create a domain

```bash
icewarp-api domains create-domain --domainstr newdomain.com
```

## Get all accounts (across every domain)

Accounts are listed per-domain (`GetAccountsInfoList` requires
`--domainstr`) - there is no single "all accounts on the server" endpoint.
Use the built-in `get-all-accounts` command, which lists every domain, then
paginates through the accounts in each, returning one combined list:

```bash
icewarp-api get-all-accounts
icewarp-api get-all-accounts --domain example.com   # restrict to one domain
icewarp-api get-all-accounts --page-size 200         # tune pagination
```

This is a curated helper (composed of `GetDomainsInfoList` +
`GetAccountsInfoList` calls), not a literal 1:1 endpoint wrapper - it's the
CLI equivalent of `IceWarpAPI.get_all_accounts()` in Python, see
[`examples/list_all_accounts.py`](list_all_accounts.py).

If you'd rather do it manually (e.g. to customize the loop), you can
combine the raw commands yourself, e.g. with `jq` in a shell script:

```bash
for domain in $(icewarp-api domains get-domains-info-list | jq -r '.item[].name'); do
  echo "=== $domain ==="
  icewarp-api accounts get-accounts-info-list --domainstr "$domain"
done
```

## Generic passthrough for any of the 174 endpoints

Useful for endpoints you don't want a typed command for, or new endpoints
added after this library was last regenerated:

```bash
icewarp-api call GetDomainsInfoList
icewarp-api call GetAccountsInfoList --param domainstr=example.com
icewarp-api call GetDomainsInfoList --param 'filter={"namemask": "*"}'
```

## Disabling TLS verification (self-signed certificates)

```bash
icewarp-api --insecure --url https://192.168.1.10:32001/icewarpapi domains get-domains-info-list
```

## Skipping the session cache

Disables reading/writing `~/.icewarp_api/session.json` entirely, so
`--url`/`--email`/`--password` (or the env vars) are required on every call:

```bash
icewarp-api --no-session-cache --url https://mail.example.com:32001/icewarpapi --email admin@example.com --password hunter2 domains get-domains-info-list
```
